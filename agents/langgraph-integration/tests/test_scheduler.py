"""Periodic scheduler: errors, interval, signals."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sync.pipeline import SyncPushResult
from sync.scheduler import run_periodic_sync


def _ok_result() -> SyncPushResult:
    return SyncPushResult(
        chunks_sent=1,
        entities_pushed=1,
        edges_pushed=0,
        skipped_unchanged=0,
    )


class TestPeriodicSync(unittest.TestCase):
    def test_continues_after_failure(self) -> None:
        calls = {"n": 0}

        def tick() -> SyncPushResult:
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("langgraph down")
            return _ok_result()

        with mock.patch("sync.scheduler.time.sleep"):
            with mock.patch("sync.scheduler.time.monotonic", side_effect=[0.0, 0.1, 0.1, 0.2]):
                stats = run_periodic_sync(
                    tick, interval_sec=1.0, max_iterations=2, stop_on_signal=False
                )
        self.assertEqual(stats.iterations, 2)
        self.assertEqual(stats.failures, 1)

    def test_precise_interval_sleep(self) -> None:
        with mock.patch("sync.scheduler.time.sleep") as sleep:
            with mock.patch(
                "sync.scheduler.time.monotonic",
                side_effect=[0.0, 0.4, 0.4, 0.9],
            ):
                run_periodic_sync(
                    _ok_result,
                    interval_sec=1.0,
                    max_iterations=2,
                    stop_on_signal=False,
                )
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args[0][0], 0.6, places=2)

    def test_stop_on_signal(self) -> None:
        handler = None

        def capture(fn):
            nonlocal handler
            handler = fn

        calls = {"n": 0}

        def tick() -> SyncPushResult:
            calls["n"] += 1
            if calls["n"] == 1 and handler is not None:
                handler(__import__("signal").SIGINT, None)
            return _ok_result()

        import signal as signal_mod

        with mock.patch("sync.scheduler.time.sleep"):
            with mock.patch("sync.scheduler.time.monotonic", side_effect=[0.0, 0.0, 1.0]):
                with mock.patch("sync.scheduler._register_stop_signals", side_effect=capture):
                    stats = run_periodic_sync(
                        tick, interval_sec=10.0, max_iterations=10, stop_on_signal=True
                    )
        self.assertEqual(stats.iterations, 1)

    def test_retry_tick(self) -> None:
        calls = {"n": 0}

        def tick() -> SyncPushResult:
            calls["n"] += 1
            if calls["n"] < 2:
                raise TimeoutError("retry me")
            return _ok_result()

        with mock.patch("sync.scheduler.time.sleep"):
            with mock.patch("sync.scheduler.time.monotonic", side_effect=[0.0, 0.0, 1.0]):
                with mock.patch("sync.retry.time.sleep"):
                    stats = run_periodic_sync(
                        tick,
                        interval_sec=1.0,
                        max_iterations=1,
                        stop_on_signal=False,
                        retry_tick=True,
                    )
        self.assertEqual(stats.iterations, 1)
        self.assertEqual(stats.failures, 0)
        self.assertEqual(calls["n"], 2)


if __name__ == "__main__":
    unittest.main()
