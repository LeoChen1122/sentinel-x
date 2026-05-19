#!/usr/bin/env python3
"""Agent phase A/B demo: inspection narrative from mock multicluster graph."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent import build_inspection_report, llm_enabled  # noqa: E402
from testing.multicluster_fixtures import (  # noqa: E402
    CLUSTER_DEV,
    CLUSTER_PROD,
    dual_cluster_rich_batch,
)


def _print_linked(title: str, items: list) -> None:
    print(f"  {title}:")
    for item in items:
        print(
            f"    - {item.get('entity_id')} "
            f"({item.get('entity_type')}, relation={item.get('relation')})"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspection narrative demo")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Enable OpenAI polish (requires SENTINEL_LLM_ENABLED=1 and OPENAI_API_KEY)",
    )
    args = parser.parse_args()

    if args.llm and not llm_enabled():
        print(
            "Note: --llm requested but LLM not enabled (set SENTINEL_LLM_ENABLED=1 "
            "and OPENAI_API_KEY). Falling back to template.",
            file=sys.stderr,
        )

    batch = dual_cluster_rich_batch()
    payload = batch.to_dict(wire_only=True)
    use_llm = True if args.llm else False

    print("=== entity counts by cluster ===")
    by_cluster: dict[str, Counter[str]] = {}
    for ent in batch.entities:
        cid = str(ent.properties.get("cluster_id", "?"))
        by_cluster.setdefault(cid, Counter())[ent.type.value] += 1
    for cid, counts in sorted(by_cluster.items()):
        print(f"  {cid}: {dict(counts)}")

    for cid, pod in ((CLUSTER_DEV, "shared-pod"), (CLUSTER_PROD, "shared-pod")):
        print(f"\n=== inspection report: {cid} / {pod} ===")
        report = build_inspection_report(
            payload,
            cluster_id=cid,
            namespace="default",
            pod_name=pod,
            use_llm=use_llm if args.llm else False,
        )
        print(f"narrative_source: {report.get('narrative_source', 'template')}")
        print(f"summary: {report['summary']}")
        print(f"pod_entity_id: {report['pod_entity_id']}")
        for sec in report["sections"]:
            print(f"  section: {sec['title']}")
        _print_linked("linked_events", report["linked_events"])
        _print_linked("linked_pods", report["linked_pods"])
        _print_linked("linked_inspections", report["linked_inspections"])
        print("--- markdown ---")
        print(report["markdown"])

    print("\nOK: inspect narrative demo complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
