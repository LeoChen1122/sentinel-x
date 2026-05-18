"""Retry helpers for LangGraph sync pushes."""

from __future__ import annotations

import logging
import os
import random
import time
from collections.abc import Callable
from typing import TypeVar

from utils.errors import LangGraphSyncError

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE_HTTP = frozenset({429, 502, 503, 504})


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _parse_delays(raw: str) -> tuple[float, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return (0.5, 1.0, 2.0)
    return tuple(float(p) for p in parts)


def sync_max_attempts() -> int:
    raw = os.getenv("LANGGRAPH_SYNC_MAX_RETRIES", "3").strip() or "3"
    try:
        n = int(raw)
    except ValueError:
        return 3
    return max(1, n)


def sync_retry_delays() -> tuple[float, ...]:
    raw = os.getenv("LANGGRAPH_SYNC_RETRY_DELAYS", "0.5,1.0,2.0")
    return _parse_delays(raw)


def sync_retry_exponential() -> bool:
    return _env_bool("LANGGRAPH_SYNC_RETRY_EXPONENTIAL", True)


def sync_retry_jitter() -> bool:
    return _env_bool("LANGGRAPH_SYNC_RETRY_JITTER", True)


def compute_retry_delay(
    attempt: int,
    backoff: tuple[float, ...],
    *,
    exponential: bool | None = None,
    jitter: bool | None = None,
) -> float:
    """Seconds to sleep before retry ``attempt`` (0-based, after a failure)."""
    if not backoff:
        return 0.0
    base = backoff[min(attempt, len(backoff) - 1)]
    use_exp = exponential if exponential is not None else sync_retry_exponential()
    delay = base * (2**attempt) if use_exp else base
    use_jitter = jitter if jitter is not None else sync_retry_jitter()
    if use_jitter and delay > 0:
        delay = delay * (0.5 + random.random())
    return delay


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, LangGraphSyncError)):
        return True
    try:
        import httpx
    except ImportError:
        httpx = None  # type: ignore[misc, assignment]
    if httpx is not None:
        if isinstance(exc, httpx.RequestError):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in _RETRYABLE_HTTP
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status in _RETRYABLE_HTTP:
        return True
    return False


def retry_call(
    fn: Callable[[], T],
    *,
    max_attempts: int | None = None,
    delays: tuple[float, ...] | None = None,
    exponential: bool | None = None,
    jitter: bool | None = None,
) -> T:
    """Call ``fn`` with retries on :func:`is_retryable` failures."""
    attempts = max_attempts if max_attempts is not None else sync_max_attempts()
    backoff = delays if delays is not None else sync_retry_delays()
    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except BaseException as e:
            last = e
            if not is_retryable(e) or attempt >= attempts - 1:
                raise
            delay = compute_retry_delay(
                attempt, backoff, exponential=exponential, jitter=jitter
            )
            logger.warning(
                "Retry %d/%d after %.2fs due to %s: %s",
                attempt + 1,
                attempts,
                delay,
                type(e).__name__,
                e,
            )
            if delay > 0:
                time.sleep(delay)
    assert last is not None
    raise last
