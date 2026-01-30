from typing import Dict, Any, List
import os
import json

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from backend.config.settings import settings

# Load settings
QDRANT_URL = settings.QDRANT_URL
QDRANT_API_KEY = settings.QDRANT_API_KEY
OPENAI_API_KEY = settings.OPENAI_API_KEY
EMBEDDING_MODEL = settings.EMBEDDING_MODEL
INCIDENTS_COLLECTION = settings.QDRANT_COLLECTION
MAX_SIMILAR_INCIDENTS = settings.MAX_SIMILAR_INCIDENTS
SIMILARITY_THRESHOLD = settings.SIMILARITY_THRESHOLD

# Sample incidents for seeding (used when collection is empty)
SEED_INCIDENTS = [
    {
        "id": "INC-2024-001",
        "title": "API Gateway OOM Crash",
        "patterns": ["high_memory", "oom_killed", "crash_loop"],
        "root_cause": "Memory leak in version 2.3.1 due to unclosed database connections",
        "resolution": "Rolled back to version 2.3.0, then deployed hotfix 2.3.2",
        "service": "api-gateway",
        "date": "2024-01-10",
        "description": "API Gateway service experienced out-of-memory crashes with high memory usage patterns and crash loops. Root cause was traced to unclosed database connections in version 2.3.1.",
    },
    {
        "id": "INC-2024-002",
        "title": "Payment Service High Latency",
        "patterns": ["high_latency", "high_cpu", "connection_errors"],
        "root_cause": "Database connection pool exhausted due to slow queries",
        "resolution": "Increased connection pool size, added query timeout, optimized slow queries",
        "service": "payment-service",
        "date": "2024-01-05",
        "description": "Payment service experienced high latency with CPU spikes and connection errors. Database connection pool was exhausted by slow queries.",
    },
    {
        "id": "INC-2024-003",
        "title": "Auth Service 5xx Errors",
        "patterns": ["high_error_rate", "timeout_errors"],
        "root_cause": "Redis cache node failed, causing auth token lookups to fail",
        "resolution": "Restarted Redis, implemented fallback to database",
        "service": "auth-service",
        "date": "2024-01-08",
        "description": "Auth service returned 5xx errors due to Redis cache node failure. Token lookups failed causing widespread authentication failures.",
    },
    {
        "id": "INC-2023-050",
        "title": "API Gateway CPU Spike",
        "patterns": ["high_cpu", "recent_deployment"],
        "root_cause": "Inefficient regex in request validation added in v2.2.0",
        "resolution": "Rolled back deployment, fixed regex pattern",
        "service": "api-gateway",
        "date": "2023-12-15",
        "description": "API Gateway experienced CPU spikes after deployment of v2.2.0. Inefficient regex pattern in request validation was consuming excessive CPU.",
    },
    {
        "id": "INC-2024-004",
        "title": "Order Service Pod Failures",
        "patterns": ["pod_failures", "probe_failure", "high_error_rate"],
        "root_cause": "Kubernetes liveness probe timeout was too aggressive",
        "resolution": "Increased probe timeout and initial delay, added readiness probe",
        "service": "order-service",
        "date": "2024-02-01",
        "description": "Order service pods were failing health checks and restarting. Liveness probe timeout was too short for startup time.",
    },
    {
        "id": "INC-2024-005",
        "title": "Notification Service Memory Leak",
        "patterns": ["high_memory", "crash_loop", "recent_deployment"],
        "root_cause": "Memory leak in new message queue consumer introduced in v3.1.0",
        "resolution": "Deployed hotfix v3.1.1 with proper message acknowledgment",
        "service": "notification-service",
        "date": "2024-02-15",
        "description": "Notification service had memory leak after v3.1.0 deployment. Messages were not being properly acknowledged, causing memory buildup.",
    },
]


class QdrantIncidentStore:
    """
    Qdrant-based vector store for incident similarity search.
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str = INCIDENTS_COLLECTION,
    ):
        """
        Initialize Qdrant incident store.

        Args:
            url: Qdrant server URL (defaults to localhost:6333 or env var)
            api_key: Qdrant API key (optional, for cloud)
            collection_name: Name of the collection to use
        """
        self.url = url or QDRANT_URL
        self.api_key = api_key or QDRANT_API_KEY
        self.collection_name = collection_name

        # Initialize Qdrant client
        if self.api_key:
            self.client = QdrantClient(url=self.url, api_key=self.api_key)
        else:
            self.client = QdrantClient(url=self.url)

        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY,
        )
        self.embedding_dim = 1536  # text-embedding-3-small dimension

    def ensure_collection(self) -> None:
        """
        Ensure the collection exists, create if not.
        """
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            print(f"[Qdrant] Created collection: {self.collection_name}")

    def seed_incidents(self, incidents: List[Dict[str, Any]] | None = None) -> None:
        """
        Seed the collection with incidents if empty.

        Args:
            incidents: List of incidents to seed (uses defaults if None)
        """
        incidents = incidents or SEED_INCIDENTS

        # Check if collection has data
        collection_info = self.client.get_collection(self.collection_name)
        if collection_info.points_count > 0:
            print(f"[Qdrant] Collection already has {collection_info.points_count} incidents")
            return

        # Generate embeddings and insert
        points = []
        for i, incident in enumerate(incidents):
            # Create searchable text from incident
            text = self._incident_to_text(incident)
            embedding = self.embeddings.embed_query(text)

            point = PointStruct(
                id=i,
                vector=embedding,
                payload={
                    "incident_id": incident["id"],
                    "title": incident["title"],
                    "patterns": incident["patterns"],
                    "root_cause": incident["root_cause"],
                    "resolution": incident["resolution"],
                    "service": incident["service"],
                    "date": incident["date"],
                    "description": incident.get("description", ""),
                },
            )
            points.append(point)

        self.client.upsert(collection_name=self.collection_name, points=points)
        print(f"[Qdrant] Seeded {len(points)} incidents")

    def _incident_to_text(self, incident: Dict[str, Any]) -> str:
        """
        Convert incident to searchable text.
        """
        patterns_str = ", ".join(incident.get("patterns", []))
        return (
            f"{incident.get('title', '')}. "
            f"Patterns: {patterns_str}. "
            f"Root cause: {incident.get('root_cause', '')}. "
            f"Service: {incident.get('service', '')}. "
            f"{incident.get('description', '')}"
        )

    def search_similar(
        self,
        patterns: List[Dict[str, Any]],
        service: str | None = None,
        limit: int = 3,
        score_threshold: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar incidents based on patterns.

        Args:
            patterns: List of detected patterns with type and description
            service: Optional service name to filter/boost
            limit: Maximum number of results
            score_threshold: Minimum similarity score

        Returns:
            List of similar incidents with similarity scores
        """
        # Build query text from patterns
        pattern_types = [p.get("type", "") for p in patterns]
        pattern_descriptions = [p.get("description", "") for p in patterns]

        query_text = f"Patterns: {', '.join(pattern_types)}. {' '.join(pattern_descriptions)}"

        # Generate embedding for query
        query_embedding = self.embeddings.embed_query(query_text)

        # Build filter if service specified
        search_filter = None
        if service:
            search_filter = Filter(
                should=[
                    FieldCondition(
                        key="service",
                        match=MatchValue(value=service),
                    )
                ]
            )

        # Search Qdrant
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=limit * 2,  # Get more to filter by threshold
            score_threshold=score_threshold,
        )

        # Convert results to incident format
        similar_incidents = []
        for result in results[:limit]:
            payload = result.payload
            similar_incidents.append(
                {
                    "id": payload.get("incident_id"),
                    "title": payload.get("title"),
                    "similarity": round(result.score, 2),
                    "root_cause": payload.get("root_cause"),
                    "resolution": payload.get("resolution"),
                    "service": payload.get("service"),
                    "date": payload.get("date"),
                    "patterns": payload.get("patterns", []),
                }
            )

        return similar_incidents

    def add_incident(self, incident: Dict[str, Any]) -> None:
        """
        Add a new incident to the store.

        Args:
            incident: Incident data to add
        """
        # Get current max ID
        collection_info = self.client.get_collection(self.collection_name)
        new_id = collection_info.points_count

        # Generate embedding
        text = self._incident_to_text(incident)
        embedding = self.embeddings.embed_query(text)

        point = PointStruct(
            id=new_id,
            vector=embedding,
            payload={
                "incident_id": incident["id"],
                "title": incident["title"],
                "patterns": incident.get("patterns", []),
                "root_cause": incident.get("root_cause", ""),
                "resolution": incident.get("resolution", ""),
                "service": incident.get("service", ""),
                "date": incident.get("date", ""),
                "description": incident.get("description", ""),
            },
        )

        self.client.upsert(collection_name=self.collection_name, points=[point])


# Global store instance (lazy initialization)
_incident_store: QdrantIncidentStore | None = None


def get_incident_store() -> QdrantIncidentStore:
    """
    Get or create the global incident store.
    """
    global _incident_store
    if _incident_store is None:
        _incident_store = QdrantIncidentStore()
        _incident_store.ensure_collection()
        _incident_store.seed_incidents()
    return _incident_store


def search_similar_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node 2: Search for similar past incidents using Qdrant RAG.

    Uses vector embeddings to find semantically similar incidents
    based on detected patterns and service context.

    Args:
        state: Current analyzer state with patterns and alert info

    Returns:
        Updated state with similar_incidents list
    """
    print("[Analyzer] Searching similar incidents via Qdrant...")

    patterns = state.get("patterns", [])
    alert = state.get("alert", {})
    current_service = alert.get("service")

    if not patterns:
        print("[Analyzer] No patterns to search, skipping RAG")
        return {"similar_incidents": []}

    # Get incident store and search
    store = get_incident_store()
    similar_incidents = store.search_similar(
        patterns=patterns,
        service=current_service,
        limit=MAX_SIMILAR_INCIDENTS,
        score_threshold=SIMILARITY_THRESHOLD,
    )

    print(f"[Analyzer] Found {len(similar_incidents)} similar incidents")

    return {"similar_incidents": similar_incidents}
