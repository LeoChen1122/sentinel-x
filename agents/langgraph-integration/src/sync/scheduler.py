"""Periodic sync loop (step 5): caller supplies MCP fetch + sync."""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass

from sync.pipeline import SyncPushResult
from sync.retry import retry_call

logger = logging.getLogger(__name__)


@dataclass
class PeriodicSyncStats:
    """Summary after :func:`run_periodic_sync` exits."""

    iterations: int
    failures: int


def _register_stop_signals(handler: Callable[[int, object | None], None]) -> None:
    signal.signal(signal.SIGINT, handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handler)


def run_periodic_sync(
    fetch_and_sync: Callable[[], SyncPushResult],
    interval_sec: float,
    *,
    max_iterations: int | None = None,
    stop_on_signal: bool = True,
    retry_tick: bool = False,
) -> PeriodicSyncStats:
    """Run ``fetch_and_sync`` on a fixed interval until stopped or ``max_iterations``.

    - Failures are logged and **do not** stop the loop (network / LangGraph blips).
    - ``retry_tick=True`` wraps each tick in :func:`sync.retry.retry_call` (in addition
      to retries inside ``push_graph_batch_resilient``).
    - Sleep is ``max(0, interval_sec - elapsed)`` so the period stays close to
      ``interval_sec`` wall-clock between tick **starts**.
    - ``SIGINT`` / ``SIGTERM`` (when available) request graceful exit after the
      current tick.
    """
    if interval_sec <= 0:
        raise ValueError("interval_sec must be positive")

    stop_requested = False

    def _request_stop(signum: int, _frame: object | None) -> None:
        nonlocal stop_requested
        stop_requested = True
        logger.info("Received signal %s, stopping periodic sync after current tick", signum)

    if stop_on_signal:
        _register_stop_signals(_request_stop)

    n = 0
    failures = 0

    def _run_tick() -> SyncPushResult:
        if retry_tick:
            return retry_call(fetch_and_sync)
        return fetch_and_sync()

    while not stop_requested and (max_iterations is None or n < max_iterations):
        start = time.monotonic()
        try:
            result = _run_tick()
            logger.debug(
                "Periodic sync tick %d ok: chunks=%d entities=%d skipped=%d",
                n + 1,
                result.chunks_sent,
                result.entities_pushed,
                result.skipped_unchanged,
            )
        except Exception as e:
            failures += 1
            logger.error("fetch_and_sync failed on tick %d: %s", n + 1, e, exc_info=True)

        n += 1
        if stop_requested or (max_iterations is not None and n >= max_iterations):
            break

        elapsed = time.monotonic() - start
        sleep_for = max(0.0, interval_sec - elapsed)
        if sleep_for > 0:
            time.sleep(sleep_for)

    return PeriodicSyncStats(iterations=n, failures=failures)
