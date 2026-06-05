"""SQLite FTS skill store tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from skills.config import SkillsConfig
from skills.store import SqliteFtsSkillStore
from skills.writer import build_skill_markdown
from agent.diagnose import diagnose_from_gather
from agent.gather import gather_subgraph
from testing.multicluster_fixtures import CLUSTER_DEV, dual_cluster_rich_payload


class TestSkillsStore(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.store.close()
        self._tmpdir.cleanup()

    def test_index_and_search_crashloop_synonym(self) -> None:
        self.store.index_all()
        matches = self.store.search("CrashLoop OR CrashLoopBackOff", limit=3)
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "fix-crashloop-restart")

    def test_get_by_fingerprint(self) -> None:
        self.store.index_all()
        fp = "5305d707b43e48f6"
        rec = self.store.get_by_fingerprint(fp)
        self.assertIsNotNone(rec)
        assert rec is not None
        self.assertEqual(rec["name"], "fix-crashloop-restart")


class TestSkillsDedup(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        self.cfg = SkillsConfig(
            skills_dir=root,
            db_path=root / ".index" / "skills.db",
            record_enabled=True,
            search_limit=3,
        )
        (root / "records").mkdir()
        self.store = SqliteFtsSkillStore(self.cfg)
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

    def test_upsert_increments_hit_count_same_file(self) -> None:
        md = build_skill_markdown(self.gather, self.diagnosis)
        r1 = self.store.upsert_skill(md)
        r2 = self.store.upsert_skill(md)
        self.assertFalse(r2["created"])
        self.assertEqual(r2["hit_count"], 2)
        self.assertEqual(Path(r1["path"]).resolve(), Path(r2["path"]).resolve())
        records = list((self.cfg.skills_dir / "records").glob("*.md"))
        self.assertEqual(len(records), 1)

    def test_search_dedupes_fingerprint(self) -> None:
        md = build_skill_markdown(self.gather, self.diagnosis)
        self.store.upsert_skill(md)
        self.store.upsert_skill(md)
        matches = self.store.search("CrashLoop OR CrashLoopBackOff", limit=3)
        fps = [m["fingerprint"] for m in matches]
        self.assertEqual(len(fps), len(set(fps)))


if __name__ == "__main__":
    unittest.main()
