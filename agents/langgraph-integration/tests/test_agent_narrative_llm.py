"""Agent phase B: optional OpenAI LLM polish for inspection narratives."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent import build_inspection_report, build_report, gather_subgraph
from agent import llm as llm_mod
from testing.multicluster_fixtures import CLUSTER_DEV, dual_cluster_full_batch


def _mock_llm_response() -> str:
    return json.dumps(
        {
            "summary": "LLM polished summary for dev-cluster.",
            "markdown": "# LLM Polished Report\n\nMock markdown body.\n",
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

    def test_llm_disabled_uses_template(self) -> None:
        report = build_report(self.gather, use_llm=False)
        self.assertEqual(report.get("narrative_source"), "template")
        self.assertIn("Inspection report", report["markdown"])

    @mock.patch.dict("os.environ", {"SENTINEL_LLM_ENABLED": "1", "OPENAI_API_KEY": "sk-test"})
    def test_llm_polish_replaces_markdown(self) -> None:
        llm_mod.call_openai = lambda _msgs: _mock_llm_response()
        report = build_report(self.gather, use_llm=True)
        self.assertEqual(report.get("narrative_source"), "llm")
        self.assertIn("LLM Polished Report", report["markdown"])
        self.assertIn("LLM polished summary", report["summary"])

    @mock.patch.dict("os.environ", {"SENTINEL_LLM_ENABLED": "1", "OPENAI_API_KEY": "sk-test"})
    def test_llm_failure_fallback_template(self) -> None:
        def _boom(_msgs: list) -> str:
            raise RuntimeError("api down")

        llm_mod.call_openai = _boom
        report = build_report(self.gather, use_llm=True)
        self.assertEqual(report.get("narrative_source"), "template")
        self.assertIn("Inspection report", report["markdown"])

    @mock.patch.dict("os.environ", {"SENTINEL_LLM_ENABLED": "1", "OPENAI_API_KEY": "sk-test"})
    def test_linked_entities_unchanged_after_llm(self) -> None:
        template = build_report(self.gather, use_llm=False)
        llm_mod.call_openai = lambda _msgs: _mock_llm_response()
        polished = build_report(self.gather, use_llm=True)
        self.assertEqual(polished["linked_events"], template["linked_events"])
        self.assertEqual(polished["linked_pods"], template["linked_pods"])
        self.assertEqual(polished["linked_inspections"], template["linked_inspections"])

    def test_build_inspection_report_use_llm_false(self) -> None:
        report = build_inspection_report(
            self.payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="shared-pod",
            use_llm=False,
        )
        self.assertEqual(report.get("narrative_source"), "template")


if __name__ == "__main__":
    unittest.main()
