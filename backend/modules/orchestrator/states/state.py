from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, SecretStr, HttpUrl, Field


class AuthType(str, Enum):
    NONE = "none"
    BASIC = "basic"
    TOKEN = "token"
    API_KEY = "api_key"



class PrometheusConfig(BaseModel):
    url: HttpUrl = Field(..., description="Prometheus URL")
    auth_type: AuthType = Field(default=AuthType.NONE, description="Authentication type")
    username: Optional[str] = Field(None, description="Username for basic auth")
    password: Optional[SecretStr] = Field(None, description="Password for basic auth")
    token: Optional[SecretStr] = Field(None, description="Token for token auth")
    allowed_metrics_patterns: List[str] = Field(
        default=["*"],
        description="Metric patterns agent is allowed to query"
    )


class GrafanaConfig(BaseModel):
    url: HttpUrl
    api_key: SecretStr


class ElasticsearchConfig(BaseModel):
    url: HttpUrl
    api_key: Optional[SecretStr] = None
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    index_prefix: str = Field(default="logs-*")

class KubernetesConfig(BaseModel):
    in_cluster: bool = Field(default=True, description="Use in-cluster config")
    kubeconfig_path: Optional[str] = Field(None, description="Path to kubeconfig file")
    context_name: Optional[str] = Field(None, description="Kubernetes context name")
    namespace: Optional[str] = Field(None, description="Kubernetes namespace")
    forbidden_namespaces: List[str] = Field(
        default=["kube-system", "kube-public", "kube-node-lease"],
        description="Namespaces agent is not allowed to access"
    )


class SlackConfig(BaseModel):
    """Slack integration configuration."""
    bot_token: SecretStr = Field(..., description="Slack bot OAuth token (xoxb-...)")
    app_token: Optional[SecretStr] = Field(default=None,description="Slack app token for socket mode (xapp-...)")
    incidents_channel: str = Field(default="#incidents",description="Channel for incident notifications")
    updates_channel: Optional[str] = Field(default=None,description="Channel for non-urgent updates")
    
    # Approval settings
    approver_user_ids: List[str] = Field(default=[],description="Slack user IDs who can approve actions")
    approver_group_ids: List[str] = Field(default=[],description="Slack user group IDs who can approve")


class PagerDutyConfig(BaseModel):
    """PagerDuty integration configuration."""
    api_key: SecretStr
    service_id: str
    escalation_policy_id: Optional[str] = None


class ActionPermissions(BaseModel):
    """
    Defines what actions the agent can perform.
    This is critical for safety - controls what the agent can do to your infra.
    """
    
    # Actions that execute without approval
    auto_approved: List[str] = Field(
        default=[
            "query_metrics",
            "search_logs", 
            "get_pod_status",
            "list_deployments",
            "get_service_health"
        ],
        description="Read-only actions that don't need approval"
    )
    
    # Actions that require human approval
    requires_approval: List[str] = Field(
        default=[
            "restart_pod",
            "scale_deployment",
            "rollback_deployment",
            "clear_cache",
            "kill_process"
        ],
        description="Actions that need human approval before execution"
    )
    
    # Actions that are NEVER allowed
    forbidden: List[str] = Field(
        default=[
            "delete_namespace",
            "delete_pvc",
            "delete_deployment",
            "drop_database",
            "terminate_instance"
        ],
        description="Dangerous actions that are never allowed"
    )
    
    # Auto-approve for low severity incidents
    auto_approve_low_severity: bool = Field(
        default=False,
        description="Auto-approve actions for low severity incidents"
    )
    
    # Maximum severity for auto-approval
    auto_approve_max_severity: str = Field(
        default="low",
        description="Maximum severity level for auto-approval (low/medium)"
    )



class AgentBehaviorConfig(BaseModel):
    """Configuration for agent behavior and tuning."""
    
    # Monitoring
    check_interval_seconds: int = Field(
        default=60,
        description="How often to check for new alerts"
    )
    alert_cooldown_minutes: int = Field(
        default=5,
        description="Minimum time between alerts for same issue"
    )
    
    # Analysis
    max_analysis_iterations: int = Field(
        default=5,
        description="Maximum iterations for root cause analysis"
    )
    confidence_threshold: float = Field(
        default=0.7,
        description="Minimum confidence to proceed with action"
    )
    
    # Actions
    action_timeout_seconds: int = Field(
        default=300,
        description="Timeout for action execution"
    )
    max_retry_attempts: int = Field(
        default=3,
        description="Maximum retries for failed actions"
    )
    
    # Human approval
    approval_timeout_minutes: int = Field(
        default=30,
        description="How long to wait for human approval"
    )
    escalate_on_timeout: bool = Field(
        default=True,
        description="Escalate to PagerDuty if approval times out"
    )


# ============================================================================
# MAIN CONFIGURATION
# ============================================================================

class AgentConfig(BaseModel):
    """
    Complete configuration for the DevOps Incident Agent.
    
    This is the main configuration object that users fill out to connect
    the agent to their infrastructure.
    """
    
    # Data sources (what agent can SEE)
    prometheus: Optional[PrometheusConfig] = None
    grafana: Optional[GrafanaConfig] = None
    elasticsearch: Optional[ElasticsearchConfig] = None
    kubernetes: Optional[KubernetesConfig] = None
    
    # Notifications (how agent COMMUNICATES)
    slack: Optional[SlackConfig] = None
    pagerduty: Optional[PagerDutyConfig] = None
    
    # Permissions (what agent can DO)
    permissions: ActionPermissions = Field(default_factory=ActionPermissions)
    
    # Behavior tuning
    behavior: AgentBehaviorConfig = Field(default_factory=AgentBehaviorConfig)
    
    def get_configured_sources(self) -> List[str]:
        """Return list of configured data sources."""
        sources = []
        if self.prometheus:
            sources.append("prometheus")
        if self.grafana:
            sources.append("grafana")
        if self.elasticsearch:
            sources.append("elasticsearch")
        if self.kubernetes:
            sources.append("kubernetes")
        return sources
    
    def get_configured_notifications(self) -> List[str]:
        """Return list of configured notification channels."""
        channels = []
        if self.slack:
            channels.append("slack")
        if self.pagerduty:
            channels.append("pagerduty")
        return channels