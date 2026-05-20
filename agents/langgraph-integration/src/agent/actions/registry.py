"""Action handler protocol and registry lookup."""

from __future__ import annotations

from typing import Protocol

from agent.types import ActionContext, ActionRecord


class ActionHandler(Protocol):
    """Run one recommended action against cluster/pod scope."""

    def run(
        self,
        action: str,
        ctx: ActionContext,
        *,
        dry_run: bool,
        live: bool,
    ) -> ActionRecord | None:
        """Return an ``ActionRecord``, or ``None`` to skip (unknown actions)."""
        ...


def resolve_handler(action: str, registry: dict[str, ActionHandler]) -> ActionHandler:
    return registry.get(action, registry["unknown"])
