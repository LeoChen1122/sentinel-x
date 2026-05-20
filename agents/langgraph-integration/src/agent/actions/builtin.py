"""Built-in simulated action handlers (phase F registry)."""

from __future__ import annotations

from agent.actions.registry import ActionHandler, resolve_handler as _lookup_handler
from agent.types import ActionContext, ActionRecord

_BUILTIN_MESSAGES: dict[str, str] = {
    "restart_pod": "Would restart pod (simulated; no K8s API call).",
    "scale_up": "Would scale workload up (simulated).",
    "check_node_capacity": "Would check node scheduling capacity (simulated).",
    "run_inspection": "Would trigger inspection workflow (simulated).",
    "review_events": "Would open event review (simulated).",
}


class SimulatedActionHandler:
    """Emit a simulated ``ActionRecord`` (default path)."""

    def __init__(self, message: str) -> None:
        self._message = message

    def run(
        self,
        action: str,
        ctx: ActionContext,
        *,
        dry_run: bool,
        live: bool,
    ) -> ActionRecord:
        if not dry_run and live:
            raise NotImplementedError(
                f"Live handler for {action!r} is not implemented. "
                "Wire Action MCP / K8s in phase 4-0b."
            )
        return ActionRecord(
            action=action,
            target=ctx["pod_id"],
            status="simulated",
            message=self._message,
        )


class UnknownActionHandler:
    """Unknown actions are skipped (not simulated as success)."""

    def run(
        self,
        action: str,
        ctx: ActionContext,
        *,
        dry_run: bool,
        live: bool,
    ) -> ActionRecord | None:
        del ctx, dry_run, live
        return None


def build_action_registry() -> dict[str, ActionHandler]:
    registry: dict[str, ActionHandler] = {
        name: SimulatedActionHandler(msg) for name, msg in _BUILTIN_MESSAGES.items()
    }
    registry["unknown"] = UnknownActionHandler()
    return registry


ACTION_REGISTRY: dict[str, ActionHandler] = build_action_registry()


def resolve_handler(action: str) -> ActionHandler:
    return _lookup_handler(action, ACTION_REGISTRY)
