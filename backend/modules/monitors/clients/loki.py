from datetime import datetime, timedelta
from typing import List, Dict, Any
import httpx


class LokiClient:
    """
    Client for querying Loki logs.
    
    Optional - you can also use Kubernetes logs directly.
    """
    
    def __init__(self, base_url: str = "http://loki:3100"):
        self.base_url = base_url.rstrip("/")
    
    async def query_logs(
        self,
        logql: str,
        start: datetime = None,
        end: datetime = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query logs using LogQL.
        
        Args:
            logql: LogQL query (e.g., '{app="api-gateway"} |= "error"')
            start: Start time
            end: End time
            limit: Max logs to return
        
        Returns:
            List of log entries
        """
        if end is None:
            end = datetime.utcnow()
        if start is None:
            start = end - timedelta(hours=1)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/loki/api/v1/query_range",
                params={
                    "query": logql,
                    "start": int(start.timestamp() * 1e9),  # Nanoseconds
                    "end": int(end.timestamp() * 1e9),
                    "limit": limit
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
        
        logs = []
        for stream in data.get("data", {}).get("result", []):
            labels = stream.get("stream", {})
            for value in stream.get("values", []):
                timestamp_ns, log_line = value
                logs.append({
                    "timestamp": datetime.fromtimestamp(int(timestamp_ns) / 1e9).isoformat(),
                    "message": log_line,
                    "labels": labels
                })
        
        return logs
    
    async def get_service_logs(
        self,
        service: str,
        namespace: str,
        level: str = None,  # "error", "warn", etc.
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get logs for a specific service.
        """
        # Build LogQL query
        query = f'{{namespace="{namespace}", app="{service}"}}'
        
        if level:
            query += f' |= "{level}"'
        
        return await self.query_logs(query, limit=limit)