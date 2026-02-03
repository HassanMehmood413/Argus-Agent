"""
Application Settings

Centralized configuration using Pydantic Settings for environment variable management.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pydantic import Field
from typing import Optional
import json


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database Configuration
    DATABASE_URL: str = "postgresql+asyncpg://user:password@db/dbname"

    # Redis Configuration
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

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
    AUTO_APPROVE_RISK_LEVELS_RAW: Optional[str] = Field(
        default=None, validation_alias="AUTO_APPROVE_RISK_LEVELS"
    )

    # Slack Configuration (for Approval workflow)
    SLACK_BOT_TOKEN: Optional[str] = None  # xoxb-... token
    SLACK_SIGNING_SECRET: Optional[str] = None  # For webhook verification
    SLACK_DEFAULT_CHANNEL: str = "#incidents"
    SLACK_APPROVAL_TIMEOUT_HOURS: int = 24  # How long to wait for approval

    # Execution Configuration
    DEPLOYMENT_TOOL: str = "kubectl"  # Options: kubectl, helm, argocd
    EXECUTION_DRY_RUN: bool = False  # If True, simulate actions only
    EXECUTION_STOP_ON_FAILURE: bool = True  # Stop if any action fails
    EXECUTION_TIMEOUT_SECONDS: int = 300  # Timeout per action (5 min)
    EXECUTION_MAX_RETRIES: int = 3  # Max retry attempts
    EXECUTION_RETRY_DELAY: float = 1.0  # Initial retry delay in seconds
    EXECUTION_RETRY_BACKOFF: float = 2.0  # Backoff multiplier

    # Kubernetes Configuration
    K8S_IN_CLUSTER: bool = False  # True if running inside Kubernetes

    # Jira Configuration (for Postmortem tickets)
    JIRA_URL: Optional[str] = None  # https://company.atlassian.net
    JIRA_EMAIL: Optional[str] = None  # user@company.com
    JIRA_API_TOKEN: Optional[str] = None  # API token from Atlassian
    JIRA_PROJECT_KEY: str = "POST"  # Project key for postmortems
    JIRA_POSTMORTEM_ISSUE_TYPE: str = "Task"  # Issue type (Task, Bug, or custom)

    @property
    def JIRA_CONFIGURED(self) -> bool:
        """Check if Jira is properly configured."""
        return all([self.JIRA_URL, self.JIRA_EMAIL, self.JIRA_API_TOKEN])

    @property
    def AUTO_APPROVE_RISK_LEVELS(self) -> list[str]:
        """Parse risk levels from env or use default."""
        if self.AUTO_APPROVE_RISK_LEVELS_RAW is None:
            return ["none", "low"]
        v = self.AUTO_APPROVE_RISK_LEVELS_RAW.strip().strip('"').strip("'")
        if v.startswith("["):
            return json.loads(v)
        return [x.strip().strip('"').strip("'") for x in v.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()

# Global settings instance
settings = get_settings()
