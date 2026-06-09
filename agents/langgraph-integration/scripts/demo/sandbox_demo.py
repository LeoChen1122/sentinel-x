#!/usr/bin/env python3
"""W6 sandbox demo: plan + run kubectl in Docker for sentinel-sandbox namespace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent.actions.policy import action_context_from_diagnosis
from agent.execute import execute_recommended_actions
from agent.types import DiagnosisReport
from sandbox.runner import run_sandbox_for_execution


def main() -> int:
    parser = argparse.ArgumentParser(description="Sentinel-X sandbox pre-run demo")
    parser.add_argument("--cluster-id", default="dev-cluster")
    parser.add_argument("--namespace", default="sentinel-sandbox")
    parser.add_argument("--pod-name", required=True)
    parser.add_argument("--issue", default="CrashLoop", choices=["CrashLoop", "OOM"])
    parser.add_argument("--dry-run", action="store_true", help="Simulate only (no sandbox)")
    args = parser.parse_args()

    pod_id = f"pod:{args.cluster_id}:{args.namespace}:{args.pod_name}"
    actions = ["restart_pod"] if args.issue == "CrashLoop" else ["scale_up"]
    diagnosis = DiagnosisReport(
        cluster_id=args.cluster_id,
        namespace=args.namespace,
        pod_name=args.pod_name,
        pod_id=pod_id,
        issues=[args.issue],
        recommended_actions=actions,
        severity="critical",
        diagnosis_source="rules_v1",
        ok=True,
    )
    ctx = action_context_from_diagnosis(diagnosis)
    execution = execute_recommended_actions(diagnosis, dry_run=args.dry_run, context=ctx)
    print("execution:", json.dumps(dict(execution), indent=2))

    if execution.get("sandbox_pending"):
        sandbox = run_sandbox_for_execution(execution, ctx)
        print("sandbox_result:", json.dumps(dict(sandbox), indent=2))
        return 0 if sandbox.get("ok") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
