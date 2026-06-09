"""Pre-flight checks before sandbox mutating commands."""

from __future__ import annotations

from sandbox.config import SandboxConfig
from sandbox.executor import run_sandbox_command


def check_scale_up_allowed(
    pod_name: str,
    namespace: str,
    deployment_name: str,
    *,
    cfg: SandboxConfig,
    run_subprocess=None,
) -> tuple[bool, str, int]:
    """Return (allowed, reason, target_replicas). Only Deployment-owned pods may scale."""
    owner_argv = [
        "kubectl",
        "get",
        "pod",
        pod_name,
        "-n",
        namespace,
        "-o",
        "jsonpath={.metadata.ownerReferences[0].kind}",
    ]
    owner_rec = run_sandbox_command(
        owner_argv,
        cfg=cfg,
        audit_meta={
            "action": "preflight_scale_owner",
            "namespace": namespace,
            "pod": pod_name,
        },
        run_subprocess=run_subprocess,
    )
    if owner_rec.get("exit_code") != 0:
        return False, "pod not found for scale preflight", 0

    owner_kind = (owner_rec.get("stdout") or "").strip()
    if owner_kind != "ReplicaSet":
        return False, f"scale_up only allowed for Deployment pods, got owner {owner_kind!r}", 0

    dep_argv = [
        "kubectl",
        "get",
        "deployment",
        deployment_name,
        "-n",
        namespace,
        "-o",
        "jsonpath={.spec.replicas}",
    ]
    dep_rec = run_sandbox_command(
        dep_argv,
        cfg=cfg,
        audit_meta={
            "action": "preflight_scale_replicas",
            "namespace": namespace,
            "pod": pod_name,
            "deployment": deployment_name,
        },
        run_subprocess=run_subprocess,
    )
    if dep_rec.get("exit_code") != 0:
        return False, f"deployment {deployment_name!r} not found", 0

    try:
        current = int((dep_rec.get("stdout") or "0").strip() or "0")
    except ValueError:
        return False, "invalid deployment replica count", 0

    if current >= cfg.max_replicas:
        return False, f"replicas_at_cap ({current}>={cfg.max_replicas})", 0

    target = min(current + 1, cfg.max_replicas)
    return True, "ok", target
