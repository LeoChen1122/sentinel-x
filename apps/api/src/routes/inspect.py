"""Inspect trigger routes (W7)."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from deps import verify_api_token
from trigger.inspect_trigger import trigger_inspect

router = APIRouter(prefix="/v1", tags=["inspect"])


class InspectRequest(BaseModel):
    cluster_id: str = Field(default_factory=lambda: os.environ.get("CLUSTER_ID", "k3s-prod"))
    namespace: str = Field(default_factory=lambda: os.environ.get("NAMESPACE", "kube-system"))
    pod_name: str
    dry_run: bool = True
    thread_id: str | None = None
    tenant_id: str | None = None


@router.post("/inspect")
def post_inspect(
    body: InspectRequest,
    _: None = Depends(verify_api_token),
) -> dict[str, Any]:
    """Trigger one LangGraph inspect run for a pod."""
    result = trigger_inspect(
        cluster_id=body.cluster_id,
        namespace=body.namespace,
        pod_name=body.pod_name,
        dry_run=body.dry_run,
        thread_id=body.thread_id or os.environ.get("LANGGRAPH_THREAD_ID"),
        tenant_id=body.tenant_id,
    )
    return dict(result)
