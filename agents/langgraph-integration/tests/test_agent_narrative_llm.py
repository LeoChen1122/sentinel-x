"""Agent phase B: LLM narrative polish (Qwen / DashScope compatible)."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent import (
    build_inspection_with_diagnosis,
    build_report,
    gather_subgraph,
    llm as llm_mod,
)
from agent.llm import (
    DEFAULT_DASHSCOPE_BASE_URL,
    DEFAULT_LLM_MODEL,
    llm_narrative_config,
    resolve_use_llm,
)
from testing.multicluster_fixtures import (
    CLUSTER_DEV,
    dual_cluster_full_batch,
    dual_cluster_rich_batch,
)


def _mock_llm_response() -> str:
    return json.dumps(
        {
            "summary": "LLM polished summary for dev-cluster.",
            "markdown": "# LLM Polished Report\n\n## Recommended actions\n\n- restart_pod\n",
        }
    )


class TestLlmNarrative(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = dual_cluster_full_batch().to_dict(wire_only=True)
        self.gather = gather_subgraph(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
        )

    def tearDown(self) -> None:
        llm_mod.call_openai = None

    def test_default_model_qwen(self) -> None:
        with mock.patch.dict("os.environ", {"SENTINEL_LLM_MODEL": ""}, clear=False):
            self.assertEqual(llm_narrative_config()["model"], DEFAULT_LLM_MODEL)
        self.assertEqual(DEFAULT_LLM_MODEL, "qwen3.6-plus")

    def test_llm_config_china_base_url_default(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_BASE_URL"}
        with mock.patch.dict("os.environ", env, clear=True):
            cfg = llm_narrative_config()
        self.assertEqual(cfg["base_url"], DEFAULT_DASHSCOPE_BASE_URL)
        self.assertFalse(cfg["base_url_configured"])
        self.assertFalse(cfg["enable_thinking"])

    @mock.patch.dict(
        "os.environ",
        {
            "SENTINEL_LLM_ENABLED": "1",
            "DASHSCOPE_API_KEY": "sk-test",
            "SENTINEL_LLM_ENABLE_THINKING": "1",
        },
    )
    def test_invoke_passes_extra_body_when_thinking_enabled(self) -> None:
        llm_mod.call_openai = None
        mock_client = mock.MagicMock()
        chunk = mock.MagicMock()
        chunk.choices = [mock.MagicMock()]
        chunk.choices[0].delta = mock.MagicMock(
            content='{"summary": "s", "markdown": "m\\n"}',
            reasoning_content="thought",
        )
        mock_client.chat.completions.create.return_value = iter([chunk])
        with mock.patch.object(llm_mod, "_make_client", return_value=mock_client):
            raw = llm_mod._invoke_openai([{"role": "user", "content": "hi"}])
        mock_client.chat.completions.create.assert_called_once()
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertTrue(kwargs.get("stream"))
        self.assertEqual(kwargs.get("extra_body"), {"enable_thinking": True})
        self.assertIn("summary", raw)

    @mock.patch.dict("os.environ", {"SENTINEL_LLM_ENABLED": "1", "DASHSCOPE_API_KEY": "sk-test"})
    def test_dashscope_api_key_alias(self) -> None:
        self.assertTrue(resolve_use_llm(None))

    def test_llm_disabled_uses_template(self) -> None:
        report = build_report(self.gather, use_llm=False)
        self.assertEqual(report.get("narrative_source"), "template")

    def test_llm_disabled_explicit_false(self) -> None:
        llm_mod.call_openai = lambda _msgs: (_ for _ in ()).throw(
            AssertionError("should not call LLM")
        )
        report = build_report(self.gather, use_llm=False)
        self.assertEqual(report.get("narrative_source"), "template")

    @mock.patch.dict("os.environ", {"SENTINEL_LLM_ENABLED": "1", "OPENAI_API_KEY": "sk-test"})
    def test_llm_polish_replaces_markdown(self) -> None:
        llm_mod.call_openai = lambda _msgs: _mock_llm_response()
        report = build_report(self.gather, use_llm=True)
        self.assertEqual(report.get("narrative_source"), "llm")
        self.assertIn("LLM Polished Report", report["markdown"])

    @mock.patch.dict("os.environ", {"SENTINEL_LLM_ENABLED": "1", "OPENAI_API_KEY": "sk-test"})
    def test_llm_failure_fallback_template(self) -> None:
        def _boom(_msgs: list) -> str:
            raise RuntimeError("api down")

        llm_mod.call_openai = _boom
        report = build_report(self.gather, use_llm=True)
        self.assertEqual(report.get("narrative_source"), "template")
        self.assertIn("api down", report.get("llm_error", ""))

    @mock.patch.dict("os.environ", {"SENTINEL_LLM_ENABLED": "1", "OPENAI_API_KEY": "sk-test"})
    def test_linked_entities_unchanged_after_llm(self) -> None:
        template = build_report(self.gather, use_llm=False)
        llm_mod.call_openai = lambda _msgs: _mock_llm_response()
        polished = build_report(self.gather, use_llm=True)
        self.assertEqual(polished["linked_events"], template["linked_events"])

    @mock.patch.dict("os.environ", {"SENTINEL_LLM_ENABLED": "1", "OPENAI_API_KEY": "sk-test"})
    def test_polish_with_diagnosis_context(self) -> None:
        seen: list[str] = []

        def _capture(msgs: list) -> str:
            seen.append(msgs[1]["content"])
            return _mock_llm_response()

        llm_mod.call_openai = _capture
        _, diagnosis, _ = build_inspection_with_diagnosis(
            dual_cluster_rich_batch().to_dict(wire_only=True),
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
            use_llm=True,
        )
        self.assertIn("CrashLoop", diagnosis["issues"])
        self.assertIn('"diagnosis"', seen[0])

    @mock.patch.dict("os.environ", {"SENTINEL_LLM_ENABLED": "1", "OPENAI_API_KEY": "sk-test"})
    def test_build_inspection_with_diagnosis_use_llm(self) -> None:
        llm_mod.call_openai = lambda _msgs: _mock_llm_response()
        narrative, diagnosis, _ = build_inspection_with_diagnosis(
            dual_cluster_rich_batch().to_dict(wire_only=True),
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
            use_llm=True,
        )
        self.assertEqual(narrative.get("narrative_source"), "llm")
        self.assertEqual(diagnosis.get("diagnosis_source"), "rules_v1")
        self.assertIn("CrashLoop", diagnosis["issues"])


if __name__ == "__main__":
    unittest.main()
