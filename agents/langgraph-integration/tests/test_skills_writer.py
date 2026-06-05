"""Skill writer tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent.diagnose import diagnose_from_gather
from agent.gather import gather_subgraph
from skills.parse import split_frontmatter
from skills.writer import build_skill_markdown
from testing.multicluster_fixtures import CLUSTER_DEV, dual_cluster_rich_payload


class TestSkillWriter(unittest.TestCase):
    def setUp(self) -> None:
        payload = dual_cluster_rich_payload()
        self.gather = gather_subgraph(
            payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
        )
        self.diagnosis = diagnose_from_gather(self.gather)

    def test_frontmatter_has_no_pod(self) -> None:
        md = build_skill_markdown(self.gather, self.diagnosis, verified=False)
        fm, body = split_frontmatter(md)
        self.assertNotIn("pod_name", fm)
        self.assertNotIn("cluster_id", fm)
        self.assertNotIn("namespace", fm)
        self.assertFalse(fm.get("verified"))

    def test_evidence_contains_pod(self) -> None:
        md = build_skill_markdown(self.gather, self.diagnosis)
        _, body = split_frontmatter(md)
        self.assertIn("pod: crash-pod", body)
        self.assertIn("cluster: dev-cluster", body)
        self.assertIn("namespace: default", body)

    def test_issues_in_frontmatter(self) -> None:
        md = build_skill_markdown(self.gather, self.diagnosis)
        fm, _ = split_frontmatter(md)
        self.assertIn("CrashLoop", fm.get("issues", []))


if __name__ == "__main__":
    unittest.main()
