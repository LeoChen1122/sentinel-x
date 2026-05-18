"""Retry backoff, jitter, and logging."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sync.retry import compute_retry_delay, is_retryable, retry_call


class TestComputeRetryDelay(unittest.TestCase):
    def test_exponential_grows(self) -> None:
        backoff = (0.5, 1.0, 2.0)
        d0 = compute_retry_delay(0, backoff, exponential=True, jitter=False)
        d1 = compute_retry_delay(1, backoff, exponential=True, jitter=False)
        self.assertEqual(d0, 0.5)  # 0.5 * 2^0
        self.assertEqual(d1, 2.0)  # 1.0 * 2^1

    def test_fixed_without_exponential(self) -> None:
        backoff = (0.5, 1.0, 2.0)
        self.assertEqual(
            compute_retry_delay(2, backoff, exponential=False, jitter=False),
            2.0,
        )

    def test_jitter_within_range(self) -> None:
        backoff = (1.0,)
        with mock.patch("sync.retry.random.random", return_value=0.0):
            self.assertEqual(
                compute_retry_delay(0, backoff, exponential=False, jitter=True),
                0.5,
            )
        with mock.patch("sync.retry.random.random", return_value=1.0):
            self.assertEqual(
                compute_retry_delay(0, backoff, exponential=False, jitter=True),
                1.5,
            )


class TestRetryCall(unittest.TestCase):
    def test_logs_on_retry(self) -> None:
        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 2:
                raise TimeoutError("timeout")
            return "ok"

        with mock.patch("sync.retry.time.sleep"):
            with mock.patch("sync.retry.compute_retry_delay", return_value=0.1):
                with self.assertLogs("sync.retry", level="WARNING") as logs:
                    self.assertEqual(
                        retry_call(
                            flaky,
                            max_attempts=3,
                            delays=(0.5,),
                            jitter=False,
                        ),
                        "ok",
                    )
        self.assertTrue(any("Retry 1/3" in m for m in logs.output))

    def test_non_retryable_raises_immediately(self) -> None:
        with self.assertRaises(ValueError):
            retry_call(lambda: (_ for _ in ()).throw(ValueError("x")), max_attempts=3)


if __name__ == "__main__":
    unittest.main()
