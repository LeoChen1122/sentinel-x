"""Action layer: dispatch recommended actions via handler registry (default simulated)."""

from __future__ import annotations

import os

from agent.actions.builtin import resolve_handler
from agent.actions.policy import action_context_from_diagnosis, validate_execution_policy
from agent.types import ActionContext, ActionRecord, DiagnosisReport, ExecutionResult

_EXECUTION_SOURCE = "registry_v1"


def _live_execute_enabled() -> bool:
    return os.environ.get("SENTINEL_EXECUTE_LIVE", "").strip() in ("1", "true", "yes")


def execute_recommended_actions(
    diagnosis: DiagnosisReport,
    *,
    dry_run: bool = True,
    context: ActionContext | None = None,
) -> ExecutionResult:
    """Map ``recommended_actions`` through the action registry; default dry-run only."""
    ctx = context or action_context_from_diagnosis(diagnosis)
    live = _live_execute_enabled()

    if not dry_run and live:
        raise NotImplementedError(
            "Live production execution is not implemented (W8+). "
            "Unset SENTINEL_EXECUTE_LIVE or use dry_run=true."
        )

    try:
        validate_execution_policy(ctx)
    except Exception as exc:
        return ExecutionResult(
            dry_run=dry_run or not live,
            sandbox_pending=False,
            actions_taken=[],
            skipped=[],
            ok=False,
            error=str(exc),
            error_stage="execute_policy",
            execution_source=_EXECUTION_SOURCE,
        )

    actions = diagnosis.get("recommended_actions") or []
    if not actions:
        return ExecutionResult(
            dry_run=dry_run or not live,
            sandbox_pending=False,
            actions_taken=[],
            skipped=[],
            ok=True,
            error=None,
            error_stage=None,
            execution_source=_EXECUTION_SOURCE,
        )

    # W6: dry_run=false without live → queue sandbox (no production writes)
    sandbox_pending = not dry_run and not live

    actions_taken: list[ActionRecord] = []
    skipped: list[str] = []

    if sandbox_pending:
        for action in actions:
            actions_taken.append(
                ActionRecord(
                    action=action,
                    target=ctx["pod_id"],
                    status="sandbox_pending",
                    message="Queued for sandbox pre-run",
                )
            )
    else:
        for action in actions:
            handler = resolve_handler(action)
            record = handler.run(action, ctx, dry_run=dry_run, live=live)
            if record is None:
                skipped.append(action)
            else:
                actions_taken.append(record)

    return ExecutionResult(
        dry_run=False if sandbox_pending else dry_run,
        sandbox_pending=sandbox_pending,
        actions_taken=actions_taken,
        skipped=skipped,
        ok=True,
        error=None,
        error_stage=None,
        execution_source=_EXECUTION_SOURCE,
    )
