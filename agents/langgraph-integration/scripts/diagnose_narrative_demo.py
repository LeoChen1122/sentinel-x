#!/usr/bin/env python3
"""Phase 5 demo: inspection narrative + diagnosis + simulated actions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent import build_inspection_with_diagnosis, llm_narrative_config  # noqa: E402
from config.tenant_registry import TenantAccessError  # noqa: E402
from testing.multicluster_fixtures import (  # noqa: E402
    CLUSTER_DEV,
    CLUSTER_PROD,
    POD_ALPHA_DEV,
    POD_ALPHA_PROD,
    POD_BETA_DEV,
    POD_BETA_PROD,
    TENANT_ALPHA,
    TENANT_BETA,
    dual_cluster_rich_batch,
    tenant_acl_matrix_payload,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnosis + narrative demo")
    parser.add_argument("--cluster-id", default=CLUSTER_DEV)
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--pod-name", default="crash-pod")
    parser.add_argument("--tenant-id", default=None)
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="Use tenant_acl_matrix_payload (for --tenant-id demos)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Enable LLM polish (Qwen via DashScope; needs SENTINEL_LLM_ENABLED=1)",
    )
    args = parser.parse_args()

    print("=== LLM config ===")
    print(json.dumps(llm_narrative_config(), indent=2, ensure_ascii=False))

    tenant_id = args.tenant_id.strip() if args.tenant_id else None
    if args.matrix or tenant_id:
        payload = tenant_acl_matrix_payload()
        pod_map = {
            (TENANT_ALPHA, CLUSTER_DEV): POD_ALPHA_DEV,
            (TENANT_ALPHA, CLUSTER_PROD): POD_ALPHA_PROD,
            (TENANT_BETA, CLUSTER_DEV): POD_BETA_DEV,
            (TENANT_BETA, CLUSTER_PROD): POD_BETA_PROD,
        }
        if tenant_id:
            pod_name = pod_map.get(
                (tenant_id, args.cluster_id),
                args.pod_name,
            )
        else:
            pod_name = args.pod_name
    else:
        payload = dual_cluster_rich_batch().to_dict(wire_only=True)
        pod_name = args.pod_name

    print(
        f"=== scope: cluster={args.cluster_id} ns={args.namespace} "
        f"pod={pod_name} tenant={tenant_id or '(none)'} ==="
    )
    try:
        narrative, diagnosis, execution = build_inspection_with_diagnosis(
            payload,
            cluster_id=args.cluster_id,
            namespace=args.namespace,
            pod_name=pod_name,
            tenant_id=tenant_id,
            use_llm=True if args.llm else False,
            dry_run=True,
        )
    except TenantAccessError as exc:
        print(f"DENIED: {exc}")
        return 1

    print("\n--- narrative summary ---")
    print(narrative.get("summary", ""))

    print("\n--- diagnosis (JSON) ---")
    print(json.dumps(dict(diagnosis), indent=2, ensure_ascii=False))

    print("\n--- execution (simulated) ---")
    print(json.dumps(dict(execution), indent=2, ensure_ascii=False))

    print("\nOK: diagnose narrative demo complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
