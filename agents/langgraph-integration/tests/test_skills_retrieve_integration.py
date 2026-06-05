"""Skills retrieve + narrative integration (W5 acceptance)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent.diagnose import diagnose_from_gather
from agent.gather import gather_subgraph
from agent.narrative import build_report_template
from skills.config import SkillsConfig
from skills.retrieve import retrieve_for_diagnosis
from skills.store import SqliteFtsSkillStore
from testing.multicluster_fixtures import CLUSTER_DEV, dual_cluster_rich_payload


class TestSkillsRetrieveIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        self.cfg = SkillsConfig(
            skills_dir=root,
            db_path=root / ".index" / "skills.db",
            record_enabled=True,
            search_limit=3,
        )
        examples = root / "examples"
        examples.mkdir()
        repo_example = Path(__file__).resolve().parents[3] / "skills" / "examples" / "fix-crashloop-restart.md"
        (examples / "fix-crashloop-restart.md").write_text(
            repo_example.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.store = SqliteFtsSkillStore(self.cfg)
        self.store.index_all()

        payload = dual_cluster_rich_payload()
        self.gather = gather_subgraph(
            payload,
            cluster_id=CLUSTER_DEV,
            namespace="default",
            pod_name="crash-pod",
        )
        self.diagnosis = diagnose_from_gather(self.gather)

    def tearDown(self) -> None:
        self.store.close()
        self._tmpdir.cleanup()

    def test_second_crashloop_hits_skill_in_narrative(self) -> None:
        matches = retrieve_for_diagnosis(self.diagnosis, store=self.store)
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "fix-crashloop-restart")

        report = build_report_template(self.gather, skill_matches=matches)
        self.assertIn("Similar past skills", report["markdown"])
        self.assertIn("fix-crashloop-restart", report["markdown"])

    def test_build_inspection_with_diagnosis_includes_skills(self) -> None:
        from agent.inspect import build_inspection_with_diagnosis

        payload = dual_cluster_rich_payload()
        with mock.patch("skills.retrieve.get_default_store", return_value=self.store):
            narrative, diagnosis, _execution = build_inspection_with_diagnosis(
                payload,
                cluster_id=CLUSTER_DEV,
                namespace="default",
                pod_name="crash-pod",
                use_llm=False,
            )
        self.assertIn("CrashLoop", diagnosis["issues"])
        self.assertIn("Similar past skills", narrative["markdown"])


if __name__ == "__main__":
    unittest.main()
