import logging
import json
from typing import Dict, Any
from datetime import datetime

from fastapi import HTTPException, BackgroundTasks, Request

from backend.modules.orchestrator import process_incident, get_incident_state, resume_incident
from backend.config.settings import settings
from backend.routes_modules.agent.schemas import (
    CreateIncidentRequest,
    IncidentResponse,
    IncidentStatusResponse,
    ResumeIncidentRequest,
    AlertManagerWebhook,
)
from backend.routes_modules.agent.utils import (
    _process_incident_background,
    handle_button_click,
    handle_modal_submission,
)

logger = logging.getLogger(__name__)


class IncidentRepository:
    """Repository for incident-related operations."""

    async def create_incident(
        self,
        request: CreateIncidentRequest,
        background_tasks: BackgroundTasks,
    ) -> IncidentResponse:
        """Create and process a new incident."""

        logger.info(f"[API] Received incident request: {request.alert.alertname}")

        # Convert alert to dict
        alert_dict = request.alert.model_dump()

        # Generate incident ID if not provided
        incident_id = request.incident_id
        if not incident_id:
            date_str = datetime.utcnow().strftime("%Y%m%d")
            import uuid
            incident_id = f"INC-{date_str}-{uuid.uuid4().hex[:6].upper()}"

        logger.info(f"[API] Processing incident {incident_id}")

        if request.async_processing:
            # Process asynchronously
            background_tasks.add_task(
                _process_incident_background,
                alert=alert_dict,
                severity=request.severity or alert_dict.get("severity", "medium"),
                incident_id=incident_id,
                slack_channel=request.slack_channel,
            )

            return IncidentResponse(
                incident_id=incident_id,
                status="processing",
                message="Incident created and processing started. Use GET /incidents/{id} to check status.",
                async_processing=True,
            )
        else:
            # Process synchronously (may timeout)
            try:
                result = await process_incident(
                    alert=alert_dict,
                    severity=request.severity or alert_dict.get("severity", "medium"),
                    incident_id=incident_id,
                    slack_channel=request.slack_channel,
                )

                return IncidentResponse(
                    incident_id=incident_id,
                    status=result.get("status", "unknown"),
                    message=f"Incident processed. Final status: {result.get('status')}",
                    async_processing=False,
                )
            except Exception as e:
                logger.error(f"[API] Error processing incident {incident_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    async def get_incident(self, incident_id: str) -> IncidentStatusResponse:
        """Get incident status by ID."""

        logger.info(f"[API] Getting status for incident {incident_id}")

        state = await get_incident_state(incident_id)

        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Incident {incident_id} not found"
            )

        return IncidentStatusResponse(
            incident_id=state.get("incident_id", incident_id),
            status=state.get("status", "unknown"),
            severity=state.get("severity"),
            created_at=state.get("created_at"),
            updated_at=state.get("updated_at"),
            root_cause=state.get("root_cause"),
            confidence=state.get("confidence"),
            approved=state.get("approved"),
            approved_by=state.get("approved_by"),
            all_succeeded=state.get("all_succeeded"),
            summary=state.get("summary"),
            error=state.get("error"),
        )

    async def resume_incident_endpoint(
        self,
        incident_id: str,
        request: ResumeIncidentRequest,
    ) -> IncidentResponse:
        """Resume a paused incident with a decision."""

        logger.info(f"[API] Resuming incident {incident_id} with decision: {request.decision}")

        try:
            result = await resume_incident(incident_id, request.decision)

            return IncidentResponse(
                incident_id=incident_id,
                status=result.get("status", "unknown"),
                message=f"Incident resumed. New status: {result.get('status')}",
                async_processing=False,
            )
        except Exception as e:
            logger.error(f"[API] Error resuming incident {incident_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def alertmanager_webhook(
        self,
        payload: AlertManagerWebhook,
        background_tasks: BackgroundTasks,
    ) -> Dict[str, Any]:
        """Handle Prometheus AlertManager webhook."""

        logger.info(
            f"[AlertManager] Received webhook: status={payload.status}, "
            f"alerts_count={len(payload.alerts)}"
        )

        processed_incidents = []
        skipped_alerts = []

        for alert in payload.alerts:
            # Skip resolved alerts (just log them)
            if alert.status == "resolved":
                logger.info(f"[AlertManager] Alert resolved: {alert.labels.get('alertname')}")
                skipped_alerts.append({
                    "alertname": alert.labels.get("alertname"),
                    "reason": "resolved"
                })
                continue

            # Extract alert data
            alertname = alert.labels.get("alertname", "UnknownAlert")
            service = alert.labels.get("service") or alert.labels.get("job", "unknown")
            namespace = alert.labels.get("namespace", "default")
            severity = alert.labels.get("severity", "medium")

            # Generate incident ID using fingerprint if available
            if alert.fingerprint:
                incident_id = f"INC-{alert.fingerprint[:12].upper()}"
            else:
                date_str = datetime.utcnow().strftime("%Y%m%d")
                import uuid
                incident_id = f"INC-{date_str}-{uuid.uuid4().hex[:6].upper()}"

            alert_dict = {
                "alertname": alertname,
                "service": service,
                "namespace": namespace,
                "severity": severity,
                "labels": alert.labels,
                "annotations": alert.annotations,
            }

            logger.info(f"[AlertManager] Processing alert: {alertname} -> {incident_id}")

            # Process asynchronously
            background_tasks.add_task(
                _process_incident_background,
                alert=alert_dict,
                severity=severity,
                incident_id=incident_id,
                slack_channel=settings.SLACK_DEFAULT_CHANNEL,
            )

            processed_incidents.append({
                "incident_id": incident_id,
                "alertname": alertname,
                "severity": severity,
            })

        return {
            "status": "accepted",
            "processed": len(processed_incidents),
            "skipped": len(skipped_alerts),
            "incidents": processed_incidents,
        }

    async def grafana_webhook(
        self,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> Dict[str, Any]:
        """Handle Grafana alerting webhook."""

        body = await request.json()
        logger.info(f"[Grafana] Received webhook: {body.get('status', 'unknown')}")

        # Grafana sends alerts in different formats depending on version
        alerts = body.get("alerts", [body])  # May be single alert or list

        processed_incidents = []

        for alert in alerts:
            status = alert.get("status", "firing")

            if status != "firing":
                logger.info(f"[Grafana] Skipping non-firing alert: {status}")
                continue

            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})

            alertname = labels.get("alertname") or alert.get("ruleName", "GrafanaAlert")
            service = labels.get("service", "unknown")
            namespace = labels.get("namespace", "default")
            severity = labels.get("severity", "medium")

            date_str = datetime.utcnow().strftime("%Y%m%d")
            import uuid
            incident_id = f"INC-{date_str}-{uuid.uuid4().hex[:6].upper()}"

            alert_dict = {
                "alertname": alertname,
                "service": service,
                "namespace": namespace,
                "severity": severity,
                "labels": labels,
                "annotations": annotations,
            }

            background_tasks.add_task(
                _process_incident_background,
                alert=alert_dict,
                severity=severity,
                incident_id=incident_id,
                slack_channel=settings.SLACK_DEFAULT_CHANNEL,
            )

            processed_incidents.append({
                "incident_id": incident_id,
                "alertname": alertname,
            })

        return {
            "status": "accepted",
            "processed": len(processed_incidents),
            "incidents": processed_incidents,
        }

    async def agent_health(self) -> Dict[str, Any]:
        """Health check for the agent system."""

        return {
            "status": "healthy",
            "service": "devops-agent",
            "timestamp": datetime.utcnow().isoformat(),
            "integrations": {
                "slack_configured": bool(settings.SLACK_BOT_TOKEN),
                "slack_channel": settings.SLACK_DEFAULT_CHANNEL if settings.SLACK_BOT_TOKEN else None,
            },
            "endpoints": {
                "create_incident": "POST /agent/incidents",
                "alertmanager_webhook": "POST /agent/incidents/alertmanager",
                "grafana_webhook": "POST /agent/incidents/grafana",
                "get_incident": "GET /agent/incidents/{incident_id}",
                "slack_interactions": "POST /agent/slack/interactions",
            }
        }

    async def handle_slack_interaction(self, body: bytes) -> Dict[str, Any]:
        """
        Handle Slack interactive component callbacks.

        This is called when a user clicks Approve/Reject/Modify buttons.
        """
        print("=" * 60)
        print("[SLACK INTERACTION] Received Slack interaction webhook!")
        print("=" * 60)

        # Parse the payload (Slack sends payload as form-encoded, not JSON)
        try:
            body_str = body.decode("utf-8")
            print(f"[SLACK INTERACTION] Raw body length: {len(body_str)}")

            # Handle URL-encoded payload
            if body_str.startswith("payload="):
                import urllib.parse
                payload_str = urllib.parse.unquote(body_str.replace("payload=", ""))
                payload = json.loads(payload_str)
            else:
                payload = json.loads(body_str)

        except Exception as e:
            logger.error(f"[Webhook] Failed to parse payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")

        logger.info(f"[Webhook] Received interaction: {payload.get('type')}")

        # Handle different interaction types
        interaction_type = payload.get("type")

        if interaction_type == "block_actions":
            return await handle_button_click(payload)
        elif interaction_type == "view_submission":
            return await handle_modal_submission(payload)
        else:
            logger.warning(f"[Webhook] Unknown interaction type: {interaction_type}")
            return {"ok": True}


def get_incident_repository() -> IncidentRepository:
    """Dependency to get IncidentRepository instance."""
    return IncidentRepository()
