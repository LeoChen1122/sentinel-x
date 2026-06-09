"""Map recommended actions to kubectl argv (sandbox namespace only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from agent.types import ActionContext
from sandbox.config import SandboxConfig
from sandbox.policy import namespace_allowed
from sandbox.preflight import check_scale_up_allowed

RunSubprocess = Callable[..., Any]


@dataclass(frozen=True)
class SandboxPlan:
    action: str
    argv: list[str]
    blocked: bool
    reason: str
    namespace: str
    pod_name: str
    deployment_name: str | None = None


def _deployment_from_pod(pod_name: str) -> str:
    """Derive deployment name from pod name (deployment-rs-pod hash)."""
    parts = pod_name.split("-")
    if len(parts) >= 3:
        return "-".join(parts[:-2])
    return pod_name


def plan_action(
    action: str,
    ctx: ActionContext,
    cfg: SandboxConfig,
    *,
    run_subprocess: RunSubprocess | None = None,
) -> SandboxPlan:
    ns = ctx["namespace"]
    pod = ctx["pod_name"]
    allowed_ns = cfg.namespace

    if not namespace_allowed(ns, allowed_ns):
        return SandboxPlan(
            action=action,
            argv=[],
            blocked=True,
            reason=f"namespace {ns!r} blocked; only {allowed_ns!r} allowed",
            namespace=ns,
            pod_name=pod,
        )

    if action == "restart_pod":
        deploy = _deployment_from_pod(pod)
        argv = ["kubectl", "delete", "pod", pod, "-n", ns]
        return SandboxPlan(
            action=action,
            argv=argv,
            blocked=False,
            reason="ok",
            namespace=ns,
            pod_name=pod,
            deployment_name=deploy,
        )

    if action == "scale_up":
        deploy = _deployment_from_pod(pod)
        allowed, reason, target = check_scale_up_allowed(
            pod,
            ns,
            deploy,
            cfg=cfg,
            run_subprocess=run_subprocess,
        )
        if not allowed:
            return SandboxPlan(
                action=action,
                argv=[],
                blocked=True,
                reason=reason,
                namespace=ns,
                pod_name=pod,
                deployment_name=deploy,
            )
        argv = [
            "kubectl",
            "scale",
            "deployment",
            deploy,
            f"--replicas={target}",
            "-n",
            ns,
        ]
        return SandboxPlan(
            action=action,
            argv=argv,
            blocked=False,
            reason="ok",
            namespace=ns,
            pod_name=pod,
            deployment_name=deploy,
        )

    return SandboxPlan(
        action=action,
        argv=[],
        blocked=True,
        reason=f"action {action!r} has no sandbox plan",
        namespace=ns,
        pod_name=pod,
    )
