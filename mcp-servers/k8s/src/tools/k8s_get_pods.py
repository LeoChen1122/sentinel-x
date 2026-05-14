from __future__ import annotations

import os
from typing import Any

from clients.kubernetes import KubernetesClient
from models.responses import NormalizedK8sListResponse
from utils.normalize import normalize_pod_list

K8S_GET_PODS_TOOL_META: dict[str, Any] = {
    "name": "k8s_get_pods",
    "readonly": True,
    "risk": "low",
    "category": "kubernetes",
}


def _nonempty_env(var: str | None) -> str | None:
    return var.strip() if var and var.strip() else None


def _client_kwargs_from_env() -> dict[str, Any]:
    raw = os.getenv("K8S_REQUEST_TIMEOUT", "30").strip() or "30"
    try:
        timeout = float(raw)
    except ValueError:
        timeout = 30.0
    kubeconfig_path = _nonempty_env(os.getenv("K8S_KUBECONFIG"))
    kube_context = _nonempty_env(os.getenv("K8S_CONTEXT"))
    return {
        "timeout": timeout,
        "kubeconfig_path": kubeconfig_path,
        "kube_context": kube_context,
    }


def k8s_get_pods(namespace: str, limit: int | None = None) -> dict[str, Any]:
    """List Pods in a namespace and return normalized ``{query, results}`` for agents."""
    if not namespace or not namespace.strip():
        raise ValueError("namespace must be a non-empty string")
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative when set")

    opts = _client_kwargs_from_env()
    with KubernetesClient(
        opts["timeout"],
        kube_context=opts["kube_context"],
        kubeconfig_path=opts["kubeconfig_path"],
    ) as client:
        payload = client.list_pods(namespace)

    normalized: NormalizedK8sListResponse = normalize_pod_list(
        "get_pods",
        payload,
        limit=limit,
    )
    return dict(normalized)
