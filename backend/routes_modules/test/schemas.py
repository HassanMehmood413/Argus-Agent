"""
Test Schemas

Pydantic models for test endpoints with example dummy data.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Literal
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# MONITOR MODULE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class MonitorTestRequest(BaseModel):
    """Request to test the Monitor module."""

    service: str = Field(
        default="payment-service",
        description="Service name to monitor"
    )
    namespace: str = Field(
        default="production",
        description="Kubernetes namespace"
    )
    time_range: str = Field(
        default="15m",
        description="Time range for metrics (e.g., 5m, 15m, 1h)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "service": "payment-service",
                    "namespace": "production",
                    "time_range": "15m"
                }
            ]
        }
    }


class MonitorTestResponse(BaseModel):
    """Response from Monitor module test."""

    service: str
    namespace: str
    metrics: Dict[str, Any]
    pod_status: Dict[str, Any]
    events: List[Dict[str, Any]]
    logs: List[Dict[str, Any]]
    recent_deployments: List[Dict[str, Any]]
    health_summary: str
    errors: List[str] = []


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYZER MODULE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class AnalyzerTestRequest(BaseModel):
    """Request to test the Analyzer module."""

    alert_name: str = Field(
        default="HighErrorRate",
        description="Alert name"
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        default="high",
        description="Alert severity"
    )
    service: str = Field(
        default="payment-service",
        description="Affected service"
    )
    use_llm: bool = Field(
        default=False,
        description="Use LLM for analysis (requires OPENAI_API_KEY)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "alert_name": "HighErrorRate",
                    "severity": "high",
                    "service": "payment-service",
                    "use_llm": False
                }
            ]
        }
    }


class AnalyzerTestResponse(BaseModel):
    """Response from Analyzer module test."""

    root_cause: str
    confidence: float
    evidence: List[str]
    analysis_reasoning: str
    recommended_actions: List[Dict[str, Any]]
    requires_approval: bool
    patterns_detected: List[Dict[str, Any]]


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL MODULE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class ApprovalTestRequest(BaseModel):
    """Request to test the Approval module."""

    incident_id: str = Field(
        default="INC-2026-001",
        description="Incident ID"
    )
    severity: str = Field(
        default="high",
        description="Incident severity"
    )
    root_cause: str = Field(
        default="Memory leak in payment-service causing OOM kills",
        description="Root cause from analyzer"
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence score"
    )
    recommended_actions: List[Dict[str, Any]] = Field(
        default=[
            {"type": "restart_pod", "target": "payment-service-abc123", "risk_level": "low", "description": "Restart unhealthy pod"},
            {"type": "scale_up", "target": "payment-service", "replicas": 3, "risk_level": "medium", "description": "Scale up replicas"}
        ],
        description="Actions to approve"
    )
    evidence: List[str] = Field(
        default=[
            "Memory usage at 94.5%",
            "2 pods in CrashLoopBackOff",
            "Error rate 15.3% (threshold 5%)"
        ],
        description="Evidence supporting the analysis"
    )
    send_to_slack: bool = Field(
        default=True,
        description="Actually send message to Slack (requires SLACK_BOT_TOKEN in .env)"
    )
    slack_channel: Optional[str] = Field(
        default=None,
        description="Override Slack channel (uses SLACK_DEFAULT_CHANNEL from .env if not set)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "incident_id": "INC-2026-001",
                    "severity": "high",
                    "root_cause": "Memory leak in payment-service",
                    "confidence": 0.85,
                    "recommended_actions": [
                        {"type": "restart_pod", "target": "payment-service-abc123", "risk_level": "low", "description": "Restart pod"}
                    ],
                    "evidence": ["Memory at 94%", "Pod crashed 5 times"],
                    "send_to_slack": True,
                    "slack_channel": None
                }
            ]
        }
    }


class ApprovalTestResponse(BaseModel):
    """Response from Approval module test."""

    incident_id: str
    slack_sent: bool
    slack_channel: Optional[str] = None
    slack_message_ts: Optional[str] = None
    slack_error: Optional[str] = None
    message_preview: str


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION MODULE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class ExecutionTestRequest(BaseModel):
    """Request to test the Execution module."""

    incident_id: str = Field(
        default="INC-2026-001",
        description="Incident ID"
    )
    actions: List[Dict[str, Any]] = Field(
        default=[
            {"type": "restart_pod", "target": "payment-service-abc123", "risk": "low"},
            {"type": "scale_up", "target": "payment-service", "replicas": 3, "risk": "medium"},
            {"type": "rollback", "target": "payment-service", "revision": "v1.2.3", "risk": "high"}
        ],
        description="Actions to execute"
    )
    dry_run: bool = Field(
        default=True,
        description="Simulate execution without making real changes"
    )
    stop_on_failure: bool = Field(
        default=True,
        description="Stop execution if an action fails"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "incident_id": "INC-2026-001",
                    "actions": [
                        {"type": "restart_pod", "target": "payment-service-abc123", "risk": "low"},
                        {"type": "scale_up", "target": "payment-service", "replicas": 3, "risk": "medium"}
                    ],
                    "dry_run": True,
                    "stop_on_failure": True
                }
            ]
        }
    }


class ExecutionTestResponse(BaseModel):
    """Response from Execution module test."""

    incident_id: str
    dry_run: bool
    execution_results: List[Dict[str, Any]]
    skipped_actions: List[Dict[str, Any]]
    all_succeeded: bool
    failed_action: Optional[Dict[str, Any]] = None
    execution_summary: str


# ═══════════════════════════════════════════════════════════════════════════════
# FULL PIPELINE TEST SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

class FullPipelineTestRequest(BaseModel):
    """Request to test the full incident pipeline."""

    alert_name: str = Field(
        default="HighErrorRate",
        description="Alert name"
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        default="high",
        description="Alert severity"
    )
    service: str = Field(
        default="payment-service",
        description="Affected service"
    )
    namespace: str = Field(
        default="production",
        description="Kubernetes namespace"
    )
    auto_approve: bool = Field(
        default=True,
        description="Auto-approve actions (skip human-in-the-loop)"
    )
    dry_run: bool = Field(
        default=True,
        description="Simulate execution"
    )


class FullPipelineTestResponse(BaseModel):
    """Response from full pipeline test."""

    incident_id: str
    stages_completed: List[str]
    monitor_summary: str
    analyzer_result: Dict[str, Any]
    approval_result: Dict[str, Any]
    execution_result: Dict[str, Any]
    summary_result: Optional[Dict[str, Any]] = None
    total_duration_ms: float


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY MODULE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class SummaryTestRequest(BaseModel):
    """Request to test the Summary module."""

    incident_id: str = Field(
        default="INC-2026-001",
        description="Incident ID"
    )
    severity: str = Field(
        default="high",
        description="Incident severity"
    )
    root_cause: str = Field(
        default="Memory leak in payment-service causing OOM kills",
        description="Identified root cause"
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence score"
    )
    evidence: List[str] = Field(
        default=[
            "Memory usage at 94.5%",
            "2 pods in CrashLoopBackOff",
            "Error rate 15.3% (threshold 5%)"
        ],
        description="Evidence supporting the analysis"
    )
    recommended_actions: List[Dict[str, Any]] = Field(
        default=[
            {"type": "restart_pod", "target": "payment-service-abc123", "risk_level": "low", "description": "Restart unhealthy pod"},
            {"type": "scale_up", "target": "payment-service", "replicas": 3, "risk_level": "medium", "description": "Scale up replicas"}
        ],
        description="Recommended actions"
    )
    approved_by: str = Field(
        default="john.doe",
        description="User who approved the actions"
    )
    execution_results: List[Dict[str, Any]] = Field(
        default=[
            {"action": {"type": "restart_pod", "target": "payment-service-abc123", "description": "Restart unhealthy pod"}, "success": True, "output": "Pod restarted successfully"},
            {"action": {"type": "scale_up", "target": "payment-service", "description": "Scale up replicas"}, "success": True, "output": "Scaled to 3 replicas"}
        ],
        description="Results from action execution"
    )
    all_succeeded: bool = Field(
        default=True,
        description="Whether all actions succeeded"
    )
    created_at: Optional[str] = Field(
        default=None,
        description="Incident creation timestamp (ISO format). If not provided, uses 15 minutes ago."
    )
    send_to_slack: bool = Field(
        default=False,
        description="Actually send summary to Slack (requires SLACK_BOT_TOKEN)"
    )
    slack_channel: Optional[str] = Field(
        default=None,
        description="Slack channel (uses default if not set)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "incident_id": "INC-2026-001",
                    "severity": "high",
                    "root_cause": "Memory leak in payment-service",
                    "confidence": 0.85,
                    "evidence": ["Memory at 94%", "2 crashed pods"],
                    "recommended_actions": [
                        {"type": "restart_pod", "target": "pod-123", "description": "Restart pod"}
                    ],
                    "approved_by": "john.doe",
                    "execution_results": [
                        {"action": {"type": "restart_pod", "description": "Restart pod"}, "success": True}
                    ],
                    "all_succeeded": True,
                    "send_to_slack": False
                }
            ]
        }
    }


class SummaryTestResponse(BaseModel):
    """Response from Summary module test."""

    incident_id: str
    summary: str
    resolution_time_seconds: float
    resolution_time_display: str
    slack_sent: bool
    slack_message_ts: Optional[str] = None
    slack_error: Optional[str] = None
    postmortem_ticket: Optional[str] = None
