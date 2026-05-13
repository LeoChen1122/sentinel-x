from __future__ import annotations

from typing import Any, TypedDict


class NormalizedQueryResponse(TypedDict):
    """Stable shape returned to tools / agents after normalization."""

    query: str
    result_type: str | None
    results: list[Any]
