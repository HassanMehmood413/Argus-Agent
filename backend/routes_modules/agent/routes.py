import logging
from typing import Dict, Any

from fastapi import APIRouter, BackgroundTasks, Request, Depends

from backend.routes_modules.agent.schemas import (
    CreateIncidentRequest,
    IncidentResponse,
    IncidentStatusResponse,
    ResumeIncidentRequest,
    AlertManagerWebhook,
)
from backend.routes_modules.agent.repository import IncidentRepository, get_incident_repository
from backend.routes_modules.agent.utils import verify_slack_request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/incidents", response_model=IncidentResponse)
async def create_incident(
    request: CreateIncidentRequest,
    background_tasks: BackgroundTasks,
    incident_repository: IncidentRepository = Depends(get_incident_repository),
) -> IncidentResponse:
    """Create and process a new incident."""
    return await incident_repository.create_incident(request, background_tasks)


@router.get("/incidents/{incident_id}", response_model=IncidentStatusResponse)
async def get_incident(
    incident_id: str,
    incident_repository: IncidentRepository = Depends(get_incident_repository),
) -> IncidentStatusResponse:
    """Get incident status by ID."""
    return await incident_repository.get_incident(incident_id)


@router.post("/incidents/{incident_id}/resume", response_model=IncidentResponse)
async def resume_incident_endpoint(
    incident_id: str,
    request: ResumeIncidentRequest,
    incident_repository: IncidentRepository = Depends(get_incident_repository),
) -> IncidentResponse:
    """Resume a paused incident with a decision."""
    return await incident_repository.resume_incident_endpoint(incident_id, request)


@router.post("/incidents/alertmanager", response_model=Dict[str, Any])
async def alertmanager_webhook(
    payload: AlertManagerWebhook,
    background_tasks: BackgroundTasks,
    incident_repository: IncidentRepository = Depends(get_incident_repository),
) -> Dict[str, Any]:
    """Handle Prometheus AlertManager webhook."""
    logger.info(
        f"[AlertManager] Received webhook: status={payload.status}, "
        f"alerts_count={len(payload.alerts)}"
    )
    return await incident_repository.alertmanager_webhook(payload, background_tasks)


@router.post("/incidents/grafana", response_model=Dict[str, Any])
async def grafana_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    incident_repository: IncidentRepository = Depends(get_incident_repository),
) -> Dict[str, Any]:
    """Handle Grafana alerting webhook."""
    return await incident_repository.grafana_webhook(request, background_tasks)


@router.get("/health")
async def agent_health(
    incident_repository: IncidentRepository = Depends(get_incident_repository),
) -> Dict[str, Any]:
    """Health check for the agent system."""
    return await incident_repository.agent_health()


@router.post("/slack/interactions", response_model=Dict[str, Any])
async def slack_interactions(
    body: bytes = Depends(verify_slack_request),
    incident_repository: IncidentRepository = Depends(get_incident_repository),
) -> Dict[str, Any]:
    """Handle Slack interactive component callbacks (button clicks)."""
    return await incident_repository.handle_slack_interaction(body)
