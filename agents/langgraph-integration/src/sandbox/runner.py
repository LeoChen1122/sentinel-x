"""Orchestrate sandbox runs for an execution result."""

from __future__ import annotations

from typing import Any

from agent.types import (
    ActionContext,
    ExecutionResult,
    SandboxResult,
    SandboxRunRecord,
    SandboxVerification,
)
from sandbox.audit import append_audit_line, new_run_id, utc_now_iso
from sandbox.config import SandboxConfig, sandbox_config
from sandbox.executor import run_sandbox_command
from sandbox.planner import plan_action
from sandbox.verifier import verify_restart_pod_deployment

_SANDBOX_SOURCE = "docker_v1"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def verification_to_dict(verification: SandboxVerification | None) -> dict[str, Any]:
    if not verification:
        return {}
    return {
        "pass": bool(verification.get("pass_")),
        "ready_seconds": int(verification.get("ready_seconds") or 0),
        "message": str(verification.get("message") or ""),
        "deployment": str(verification.get("deployment") or ""),
        "checked_pod": str(verification.get("checked_pod") or ""),
    }


def _to_run_record(raw: dict[str, Any], *, cfg: SandboxConfig) -> SandboxRunRecord:
    limit = cfg.payload_truncate
    return SandboxRunRecord(
        action=str(raw.get("action", "")),
        command=list(raw.get("command") or []),
        exit_code=int(raw.get("exit_code", -1)),
        status=str(raw.get("status", "failed")),
        message=str(raw.get("message", "")),
        audit_path=str(raw.get("audit_path", "")),
        run_id=str(raw.get("run_id", "")),
        blocked=bool(raw.get("blocked", False)),
        stdout=_truncate(str(raw.get("stdout") or ""), limit),
        stderr=_truncate(str(raw.get("stderr") or ""), limit),
    )


def sandbox_result_to_dict(result: SandboxResult) -> dict[str, Any]:
    out: dict[str, Any] = dict(result)
    if result.get("verification"):
        out["verification"] = verification_to_dict(result["verification"])
    return out


def run_sandbox_for_execution(
    execution: ExecutionResult,
    context: ActionContext,
    *,
    cfg: SandboxConfig | None = None,
    run_subprocess=None,
    sleep_fn=None,
    monotonic_fn=None,
) -> SandboxResult:
    """Plan and run sandbox kubectl for each action in execution."""
    cfg = cfg or sandbox_config()
    if not cfg.enabled:
        return SandboxResult(
            runs=[],
            ok=True,
            sandbox_source=_SANDBOX_SOURCE,
            skipped=True,
            message="sandbox disabled",
        )

    if not execution.get("sandbox_pending"):
        return SandboxResult(
            runs=[],
            ok=True,
            sandbox_source=_SANDBOX_SOURCE,
            skipped=True,
            message="sandbox not pending",
        )

    actions_taken = execution.get("actions_taken") or []
    actions = [str(r.get("action", "")) for r in actions_taken if r.get("action")]

    runs: list[SandboxRunRecord] = []
    any_blocked = False
    all_ok = True
    verification: SandboxVerification | None = None
    needs_verification = False

    for action in actions:
        plan = plan_action(action, context, cfg, run_subprocess=run_subprocess)
        if plan.blocked:
            any_blocked = True
            all_ok = False
            raw = {
                "run_id": new_run_id(),
                "ts": utc_now_iso(),
                "action": action,
                "command": [],
                "exit_code": -1,
                "status": "blocked",
                "message": plan.reason,
                "blocked": True,
                "namespace": plan.namespace,
                "pod": plan.pod_name,
                "stdout": "",
                "stderr": plan.reason,
            }
            path = append_audit_line(cfg.audit_dir, raw)
            raw["audit_path"] = str(path)
            runs.append(_to_run_record(raw, cfg=cfg))
            continue

        raw = run_sandbox_command(
            plan.argv,
            cfg=cfg,
            audit_meta={
                "action": action,
                "namespace": plan.namespace,
                "pod": plan.pod_name,
            },
            run_subprocess=run_subprocess,
        )
        raw["action"] = action
        record = _to_run_record(raw, cfg=cfg)
        runs.append(record)
        if record.get("status") != "ok":
            all_ok = False

        if action == "restart_pod" and record.get("status") == "ok":
            needs_verification = True
            deploy = plan.deployment_name or plan.pod_name
            verification = verify_restart_pod_deployment(
                deploy,
                plan.namespace,
                cfg=cfg,
                run_subprocess=run_subprocess,
                sleep_fn=sleep_fn,
                monotonic_fn=monotonic_fn,
            )
            if not verification.get("pass_"):
                all_ok = False

    if needs_verification and verification is not None:
        if not verification.get("pass_"):
            all_ok = False

    return SandboxResult(
        runs=runs,
        ok=all_ok and not any_blocked,
        sandbox_source=_SANDBOX_SOURCE,
        blocked=any_blocked,
        skipped=False,
        verification=verification,
    )
