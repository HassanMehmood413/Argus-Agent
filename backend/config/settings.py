"""
Application Settings

Centralized configuration using Pydantic Settings for environment variable management.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = None
    MODEL: str = "gpt-4o"

    # Qdrant Configuration
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "devops_incidents"

    # Embedding Configuration
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Analyzer Configuration
    MAX_SIMILAR_INCIDENTS: int = 3
    SIMILARITY_THRESHOLD: float = 0.3
    MAX_ACTIONS: int = 3

    # Approval Thresholds
    CONFIDENCE_THRESHOLD: float = 0.7
    AUTO_APPROVE_RISK_LEVELS: list[str] = ["none", "low"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()
