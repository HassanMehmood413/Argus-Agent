from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field

class SlackInteractionPayload(BaseModel):
    """
    Parsed Slack interaction payload.

    Slack sends this when a user clicks a button in a message.
    """
    type: str  # "block_actions" for button clicks
    user: dict  # {"id": "U123", "username": "john", "name": "John Doe"}
    channel: dict  # {"id": "C123", "name": "incidents"}
    message: dict  # The message containing the button
    actions: list  # List of actions taken
    response_url: str  # URL to send follow-up messages
    trigger_id: str  # For opening modals


# ═══════════════════════════════════════════════════════════════════════════════
# INCIDENT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class AlertData(BaseModel):
    """Alert data from monitoring system."""

    alertname: str = Field(..., description="Name of the alert")
    service: str = Field(..., description="Affected service name")
    namespace: str = Field(default="default", description="Kubernetes namespace")
    severity: Optional[str] = Field(default=None, description="Alert severity")
    labels: Optional[Dict[str, str]] = Field(default=None, description="Additional labels")
    annotations: Optional[Dict[str, str]] = Field(default=None, description="Alert annotations")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "alertname": "HighMemoryUsage",
                    "service": "api-gateway",
                    "namespace": "production",
                    "severity": "critical",
                    "labels": {"pod": "api-gateway-abc123"},
                    "annotations": {"description": "Memory usage above 90%"}
                }
            ]
        }
    }


class AlertManagerAlert(BaseModel):
    """Single alert from Prometheus AlertManager."""
    status: str  # "firing" or "resolved"
    labels: Dict[str, str]
    annotations: Dict[str, str] = {}
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None


class AlertManagerWebhook(BaseModel):
    """Prometheus AlertManager webhook payload."""
    version: str = "4"
    groupKey: Optional[str] = None
    status: str  # "firing" or "resolved"
    receiver: Optional[str] = None
    groupLabels: Dict[str, str] = {}
    commonLabels: Dict[str, str] = {}
    commonAnnotations: Dict[str, str] = {}
    externalURL: Optional[str] = None
    alerts: List[AlertManagerAlert]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "version": "4",
                    "status": "firing",
                    "receiver": "devops-agent",
                    "alerts": [
                        {
                            "status": "firing",
                            "labels": {
                                "alertname": "HighMemoryUsage",
                                "service": "api-gateway",
                                "namespace": "production",
                                "severity": "critical"
                            },
                            "annotations": {
                                "description": "Memory usage is above 90%",
                                "runbook_url": "https://wiki.example.com/runbook/memory"
                            }
                        }
                    ]
                }
            ]
        }
    }


class CreateIncidentRequest(BaseModel):
    """Request to create and process a new incident."""

    alert: AlertData = Field(..., description="Alert data")
    severity: Optional[str] = Field(
        default="medium",
        description="Incident severity (low, medium, high, critical)"
    )
    incident_id: Optional[str] = Field(
        default=None,
        description="Optional incident ID (auto-generated if not provided)"
    )
    slack_channel: Optional[str] = Field(
        default=None,
        description="Slack channel for notifications (uses default if not provided)"
    )
    async_processing: bool = Field(
        default=True,
        description="Process incident asynchronously (recommended for production)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "alert": {
                        "alertname": "HighMemoryUsage",
                        "service": "api-gateway",
                        "namespace": "production"
                    },
                    "severity": "critical",
                    "async_processing": True
                }
            ]
        }
    }


class IncidentResponse(BaseModel):
    """Response after creating an incident."""

    incident_id: str
    status: str
    message: str
    async_processing: bool = False


class IncidentStatusResponse(BaseModel):
    """Response with full incident status."""

    incident_id: str
    status: str
    severity: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    root_cause: Optional[str] = None
    confidence: Optional[float] = None
    approved: Optional[bool] = None
    approved_by: Optional[str] = None
    all_succeeded: Optional[bool] = None
    summary: Optional[str] = None
    error: Optional[str] = None


class ResumeIncidentRequest(BaseModel):
    """Request to resume a paused incident."""

    decision: Dict[str, Any] = Field(
        ...,
        description="Decision data (e.g., {'approved': True, 'approved_by': 'user'})"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "decision": {
                        "approved": True,
                        "approved_by": "john.doe",
                        "approved_by_name": "John Doe"
                    }
                }
            ]
        }
    }
