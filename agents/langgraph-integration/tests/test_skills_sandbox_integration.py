"""W6: sandbox pass → skill verified in frontmatter."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent.types import ActionContext, DiagnosisReport, ExecutionResult, GatherResult, SandboxVerification
from sandbox.config import SandboxConfig
from sandbox.runner import run_sandbox_for_execution
from skills.config import SkillsConfig
from skills.store import SqliteFtsSkillStore
from skills.writer import build_skill_markdown


class TestSkillsSandboxIntegration(unittest.TestCase):
    @mock.patch(
        "sandbox.runner.verify_restart_pod_deployment",
        return_value=SandboxVerification(
            pass_=True,
            ready_seconds=30,
            message="sandbox_pass",
            deployment="crash-demo",
            checked_pod="crash-demo-abc",
        ),
    )
    def test_verified_skill_frontmatter_after_sandbox_ok(self, _mock_verify) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kc = root / "config"
            kc.write_text("apiVersion: v1\n", encoding="utf-8")
            cfg = SandboxConfig(
                enabled=True,
                namespace="sentinel-sandbox",
                audit_dir=root / "audit",
                image="sentinel-x-sandbox:latest",
                timeout_sec=30,
                max_replicas=5,
                kubeconfig=kc,
                ready_sec=30,
                verify_poll_sec=5,
                verify_timeout_sec=120,
                payload_truncate=4096,
            )
            gather = GatherResult(
                cluster_id="dev",
                namespace="sentinel-sandbox",
                pod_name="crash-demo-abc",
                pod_entity_id="pod:dev:sentinel-sandbox:crash-demo-abc",
                subgraph={},
                queries={},
            )
            diagnosis = DiagnosisReport(
                cluster_id="dev",
                namespace="sentinel-sandbox",
                pod_name="crash-demo-abc",
                pod_id="pod:dev:sentinel-sandbox:crash-demo-abc",
                issues=["CrashLoop"],
                recommended_actions=["restart_pod"],
                severity="critical",
                diagnosis_source="rules_v1",
                ok=True,
            )
            execution = ExecutionResult(
                dry_run=False,
                sandbox_pending=True,
                actions_taken=[
                    {
                        "action": "restart_pod",
                        "target": gather["pod_entity_id"],
                        "status": "sandbox_pending",
                        "message": "q",
                    }
                ],
                skipped=[],
                ok=True,
                execution_source="registry_v1",
            )
            ctx = ActionContext(
                cluster_id="dev",
                namespace="sentinel-sandbox",
                pod_name="crash-demo-abc",
                pod_id=gather["pod_entity_id"],
                tenant_id=None,
            )

            def fake_run(cmd, **kwargs):
                return CompletedProcess(cmd, 0, stdout="deleted", stderr="")

            sandbox = run_sandbox_for_execution(
                execution, ctx, cfg=cfg, run_subprocess=fake_run
            )
            self.assertTrue(sandbox["ok"])

            verified = bool(sandbox.get("ok") and not sandbox.get("blocked"))
            md = build_skill_markdown(gather, diagnosis, verified=verified)
            self.assertIn("verified: true", md)

            skills_dir = root / "skills"
            scfg = SkillsConfig(
                skills_dir=skills_dir,
                db_path=skills_dir / ".index" / "db",
                record_enabled=True,
                search_limit=3,
            )
            store = SqliteFtsSkillStore(scfg)
            result = store.upsert_skill(md)
            self.assertTrue(result.get("created"))
            self.assertTrue(result.get("path"))
            store.close()
            text = Path(result["path"]).read_text(encoding="utf-8")
            self.assertRegex(text, r"verified:\s*true")


if __name__ == "__main__":
    unittest.main()
