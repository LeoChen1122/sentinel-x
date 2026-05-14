from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from utils.errors import PrometheusQueryError


def test_prom_query_range_matrix_success():
    from tools import prom_query_range

    payload = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"__name__": "up"},
                    "values": [[1000.0, "1"], [1015.0, "1"]],
                }
            ],
        },
    }
    with patch.object(prom_query_range, "PrometheusClient") as PC:
        inst = MagicMock()
        inst.__enter__ = MagicMock(return_value=inst)
        inst.__exit__ = MagicMock(return_value=False)
        inst.query_range.return_value = payload
        PC.return_value = inst
        r = prom_query_range.prom_query_range("up", 1000, 2000, "15s")
    assert r["query"] == "up"
    assert r["result_type"] == "matrix"
    assert len(r["results"]) == 1
    assert r["results"][0]["values"] == [[1000.0, "1"], [1015.0, "1"]]
    inst.query_range.assert_called_once_with("up", start=1000, end=2000, step="15s")


def test_prom_query_range_step_int_normalized():
    from tools import prom_query_range

    payload = {
        "status": "success",
        "data": {"resultType": "matrix", "result": []},
    }
    with patch.object(prom_query_range, "PrometheusClient") as PC:
        inst = MagicMock()
        inst.__enter__ = MagicMock(return_value=inst)
        inst.__exit__ = MagicMock(return_value=False)
        inst.query_range.return_value = payload
        PC.return_value = inst
        prom_query_range.prom_query_range("up", 1, 2, 15)
    inst.query_range.assert_called_once()
    _, kwargs = inst.query_range.call_args
    assert kwargs["step"] == "15s"


def test_prom_query_range_end_le_start_raises():
    from tools import prom_query_range

    with pytest.raises(ValueError, match="end must be greater than start"):
        prom_query_range.prom_query_range("up", 10, 10, "1s")


def test_prom_query_range_empty_promql_raises():
    from tools import prom_query_range

    with pytest.raises(ValueError, match="non-empty"):
        prom_query_range.prom_query_range("", 0, 1, "1s")


def test_prom_query_range_prometheus_query_error_propagates():
    from tools import prom_query_range

    with patch.object(prom_query_range, "PrometheusClient") as PC:
        inst = MagicMock()
        inst.__enter__ = MagicMock(return_value=inst)
        inst.__exit__ = MagicMock(return_value=False)
        inst.query_range.side_effect = PrometheusQueryError("bad_data: expr")
        PC.return_value = inst
        with pytest.raises(PrometheusQueryError):
            prom_query_range.prom_query_range("up", 0, 1, "1s")


def test_prom_query_range_invalid_step_raises():
    from tools import prom_query_range

    with pytest.raises(ValueError):
        prom_query_range.prom_query_range("up", 0, 1, 0)


def test_prom_query_range_rfc3339_skips_local_window_check():
    from tools import prom_query_range

    payload = {
        "status": "success",
        "data": {"resultType": "matrix", "result": []},
    }
    with patch.object(prom_query_range, "PrometheusClient") as PC:
        inst = MagicMock()
        inst.__enter__ = MagicMock(return_value=inst)
        inst.__exit__ = MagicMock(return_value=False)
        inst.query_range.return_value = payload
        PC.return_value = inst
        prom_query_range.prom_query_range(
            "up",
            "2020-01-02T00:00:00Z",
            "2020-01-01T00:00:00Z",
            "1m",
        )
    inst.query_range.assert_called_once()
