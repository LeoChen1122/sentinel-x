from __future__ import annotations

from typing import Any, TypedDict


class NormalizedK8sListResponse(TypedDict):
    """Stable list shape returned to tools / agents after normalization."""

    query: str
    results: list[dict[str, Any]]
