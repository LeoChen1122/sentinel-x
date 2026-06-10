"""Alertmanager webhook adapter (W7)."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import verify_api_token
from trigger.inspect_trigger import trigger_inspect

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


class AlertLabel(BaseModel):
    model_config = {"extra": "allow"}

    alertname: str | None = None
    namespace: str | None = None
    pod: str | None = None
    severity: str | None = None


class AlertItem(BaseModel):
    model_config = {"extra": "allow"}

    status: str | None = None
    labels: AlertLabel = Field(default_factory=AlertLabel)


class AlertmanagerWebhook(BaseModel):
    model_config = {"extra": "allow"}

    status: str | None = None
    alerts: list[AlertItem] = Field(default_factory=list)


def _pick_firing_alert(body: AlertmanagerWebhook) -> AlertItem | None:
    for alert in body.alerts:
        if (alert.status or "").lower() == "firing":
            return alert
    return body.alerts[0] if body.alerts else None


@router.post("/alertmanager")
def alertmanager_webhook(
    body: AlertmanagerWebhook,
    _: None = Depends(verify_api_token),
) -> dict[str, Any]:
    """Map Alertmanager webhook to inspect trigger."""
    alert = _pick_firing_alert(body)
    if alert is None:
        raise HTTPException(status_code=422, detail="no alerts in payload")

    labels = alert.labels
    pod_name = (labels.pod or "").strip()
    namespace = (labels.namespace or os.environ.get("NAMESPACE", "kube-system")).strip()
    cluster_id = os.environ.get("CLUSTER_ID", "k3s-prod").strip()

    if not pod_name:
        raise HTTPException(
            status_code=422,
            detail="alert labels must include pod (and optionally namespace)",
        )

    dry_raw = os.environ.get("SENTINEL_PATROL_DRY_RUN", "true").strip().lower()
    dry_run = dry_raw not in ("0", "false", "no", "off")

    result = trigger_inspect(
        cluster_id=cluster_id,
        namespace=namespace,
        pod_name=pod_name,
        dry_run=dry_run,
        thread_id=os.environ.get("LANGGRAPH_THREAD_ID"),
    )
    out = dict(result)
    out["alert"] = {
        "alertname": labels.alertname,
        "status": alert.status,
    }
    return out
