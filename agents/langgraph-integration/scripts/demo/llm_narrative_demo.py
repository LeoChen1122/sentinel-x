#!/usr/bin/env python3
"""Minimal LLM narrative demo (Qwen qwen3.6-plus via DashScope compatible API)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent import (  # noqa: E402
    build_inspection_with_diagnosis,
    llm_narrative_config,
)
from testing.multicluster_fixtures import CLUSTER_DEV, dual_cluster_rich_payload  # noqa: E402


def main() -> int:
    cfg = llm_narrative_config()
    print("=== LLM narrative config ===")
    print(json.dumps(cfg, indent=2, ensure_ascii=False))

    if not cfg["enabled"] and not cfg["api_key_set"]:
        print(
            "\nSet SENTINEL_LLM_ENABLED=1 and DASHSCOPE_API_KEY (or OPENAI_API_KEY), "
            "then re-run with --llm.",
            file=sys.stderr,
        )

    payload = dual_cluster_rich_payload()
    use_llm = True
    print(f"\n=== inspection + diagnosis (crash-pod, use_llm={use_llm}) ===")
    narrative, diagnosis, execution = build_inspection_with_diagnosis(
        payload,
        cluster_id=CLUSTER_DEV,
        namespace="default",
        pod_name="crash-pod",
        use_llm=use_llm,
        dry_run=True,
    )
    print(f"narrative_source: {narrative.get('narrative_source')}")
    print(f"llm_error: {narrative.get('llm_error')}")
    print(f"summary: {narrative.get('summary', '')[:200]}...")
    print(f"diagnosis issues: {diagnosis.get('issues')}")
    print(f"execution dry_run: {execution.get('dry_run')}")
    print("\nOK: llm narrative demo complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
