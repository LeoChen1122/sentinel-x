"""Post-sandbox verification (W6.1: Ready must hold for N seconds)."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from agent.types import SandboxVerification
from sandbox.config import SandboxConfig
from sandbox.executor import run_sandbox_command

RunSubprocess = Callable[..., Any]


def _pod_is_healthy(pod: dict[str, Any]) -> tuple[bool, bool]:
    """Return (ready_and_stable, crash_loop)."""
    crash_loop = False
    for st in pod.get("status", {}).get("containerStatuses") or []:
        state = st.get("state") or {}
        waiting = state.get("waiting") or {}
        reason = str(waiting.get("reason", ""))
        if "CrashLoop" in reason or "BackOff" in reason:
            crash_loop = True

    phase = str(pod.get("status", {}).get("phase", ""))
    if phase == "Failed":
        crash_loop = True

    ready = False
    for cond in pod.get("status", {}).get("conditions") or []:
        if cond.get("type") == "Ready" and cond.get("status") == "True":
            ready = True
            break

    return ready and not crash_loop, crash_loop


def _fetch_labeled_pods(
    deployment: str,
    namespace: str,
    *,
    cfg: SandboxConfig,
    run_subprocess: RunSubprocess | None,
) -> tuple[list[dict[str, Any]], str]:
    argv = [
        "kubectl",
        "get",
        "pods",
        "-l",
        f"app={deployment}",
        "-n",
        namespace,
        "-o",
        "json",
    ]
    record = run_sandbox_command(
        argv,
        cfg=cfg,
        audit_meta={
            "action": "verify_list_pods",
            "namespace": namespace,
            "deployment": deployment,
        },
        run_subprocess=run_subprocess,
    )
    if record.get("exit_code") != 0:
        return [], record.get("message") or "list pods failed"

    try:
        data = json.loads(record.get("stdout") or "{}")
    except json.JSONDecodeError:
        return [], "invalid pods json"

    items = data.get("items") or []
    return items, "ok"


def verify_restart_pod_deployment(
    deployment: str,
    namespace: str,
    *,
    cfg: SandboxConfig,
    run_subprocess: RunSubprocess | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    monotonic_fn: Callable[[], float] | None = None,
) -> SandboxVerification:
    """Poll Deployment pods until Ready holds for ``cfg.ready_sec`` or fail."""
    sleep = sleep_fn or time.sleep
    mono = monotonic_fn or time.monotonic
    deadline = mono() + cfg.verify_timeout_sec
    ready_since: float | None = None
    checked_pod = ""

    while mono() < deadline:
        pods, msg = _fetch_labeled_pods(
            deployment, namespace, cfg=cfg, run_subprocess=run_subprocess
        )
        if not pods:
            ready_since = None
            sleep(cfg.verify_poll_sec)
            continue

        any_healthy = False
        any_crash = False
        for pod in pods:
            name = str(pod.get("metadata", {}).get("name", ""))
            healthy, crash = _pod_is_healthy(pod)
            if crash:
                any_crash = True
                checked_pod = name
            if healthy:
                any_healthy = True
                checked_pod = name

        if any_crash:
            return SandboxVerification(
                pass_=False,
                ready_seconds=0,
                message="sandbox_crash_loop_returned",
                deployment=deployment,
                checked_pod=checked_pod,
            )

        if any_healthy:
            if ready_since is None:
                ready_since = mono()
            held = mono() - ready_since
            if held >= cfg.ready_sec:
                return SandboxVerification(
                    pass_=True,
                    ready_seconds=int(held),
                    message="sandbox_pass",
                    deployment=deployment,
                    checked_pod=checked_pod,
                )
        else:
            ready_since = None

        sleep(cfg.verify_poll_sec)

    return SandboxVerification(
        pass_=False,
        ready_seconds=0,
        message="sandbox_verify_timeout",
        deployment=deployment,
        checked_pod=checked_pod,
    )


# Backward-compatible alias (deprecated single-shot check)
def verify_restart_pod(
    pod_name: str,
    namespace: str,
    *,
    cfg: SandboxConfig,
    run_subprocess=None,
) -> dict[str, str]:
    """Legacy helper; prefer ``verify_restart_pod_deployment``."""
    from sandbox.planner import _deployment_from_pod

    deploy = _deployment_from_pod(pod_name)
    result = verify_restart_pod_deployment(
        deploy, namespace, cfg=cfg, run_subprocess=run_subprocess
    )
    return {
        "verified": "true" if result.get("pass_") else "false",
        "message": str(result.get("message", "")),
        "deployment": deploy,
    }
