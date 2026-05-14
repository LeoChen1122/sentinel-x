"""Cloud / real Prometheus E2E for ``prom_query_range``.

**Normalized matrix contract (UI / Agent)**

Successful range responses are normalized to a flat dict (no Prometheus
``status`` / ``data`` at the top level):

- ``query`` (str): the PromQL that was executed.
- ``result_type`` (str | None): for ``/api/v1/query_range``, Prometheus
  typically returns ``"matrix"`` (each series has ``metric`` + ``values``).
- ``results`` (list): series objects. For matrix, each element should have:

  - ``metric``: dict of label set (strings).
  - ``values``: list of ``[timestamp, sample_string]`` pairs (length-2 lists),
    suitable for time-series charts.

This module's integration tests are skipped unless
``PROMETHEUS_E2E_BASE_URL`` or ``PROMETHEUS_BASE_URL`` is set.
"""

from __future__ import annotations

import os
import time

import pytest

from tools.prom_query_range import prom_query_range


def _e2e_base_url() -> str | None:
    return os.getenv("PROMETHEUS_E2E_BASE_URL") or os.getenv("PROMETHEUS_BASE_URL")


def _assert_normalized_matrix(r: dict) -> None:
    assert set(r.keys()) == {"query", "result_type", "results"}
    assert r["query"] == "up"
    assert r["result_type"] == "matrix", f"expected matrix, got {r['result_type']!r}"
    assert isinstance(r["results"], list)
    assert len(r["results"]) >= 1, "expected at least one series from cloud up"
    for series in r["results"]:
        assert isinstance(series, dict)
        assert "metric" in series and isinstance(series["metric"], dict)
        assert "values" in series and isinstance(series["values"], list)
        assert len(series["values"]) >= 1
        pair = series["values"][0]
        assert isinstance(pair, (list, tuple)) and len(pair) == 2


@pytest.mark.integration
def test_e2e_prom_query_range_cloud_matrix():
    base = _e2e_base_url()
    if not base:
        pytest.skip("Set PROMETHEUS_E2E_BASE_URL or PROMETHEUS_BASE_URL for integration")

    os.environ["PROMETHEUS_BASE_URL"] = base
    if os.getenv("PROMETHEUS_E2E_VERIFY_SSL"):
        os.environ["PROMETHEUS_VERIFY_SSL"] = os.environ["PROMETHEUS_E2E_VERIFY_SSL"]

    end = int(time.time())
    start = end - 3600
    r = prom_query_range("up", start, end, 15)
    _assert_normalized_matrix(r)


@pytest.mark.integration
def test_e2e_prom_query_range_step_string_duration():
    base = _e2e_base_url()
    if not base:
        pytest.skip("Set PROMETHEUS_E2E_BASE_URL or PROMETHEUS_BASE_URL for integration")

    os.environ["PROMETHEUS_BASE_URL"] = base
    if os.getenv("PROMETHEUS_E2E_VERIFY_SSL"):
        os.environ["PROMETHEUS_VERIFY_SSL"] = os.environ["PROMETHEUS_E2E_VERIFY_SSL"]

    end = int(time.time())
    start = end - 1800
    r = prom_query_range("up", start, end, "15s")
    _assert_normalized_matrix(r)
