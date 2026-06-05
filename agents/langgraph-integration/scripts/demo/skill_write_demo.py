#!/usr/bin/env python3
"""Write a skill Markdown file from mock gather + diagnosis (W5 demo)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent.diagnose import diagnose_from_gather  # noqa: E402
from agent.gather import gather_subgraph  # noqa: E402
from skills.store import SqliteFtsSkillStore  # noqa: E402
from skills.config import SkillsConfig  # noqa: E402
from skills.writer import build_skill_markdown  # noqa: E402
from testing.multicluster_fixtures import CLUSTER_DEV, dual_cluster_rich_payload  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Write skill from crash-pod fixture")
    parser.add_argument("--pod-name", default="crash-pod")
    parser.add_argument("--skills-dir", default="", help="Override SENTINEL_SKILLS_DIR")
    args = parser.parse_args()

    payload = dual_cluster_rich_payload()
    gather = gather_subgraph(
        payload,
        cluster_id=CLUSTER_DEV,
        namespace="default",
        pod_name=args.pod_name,
    )
    diagnosis = diagnose_from_gather(gather)
    markdown = build_skill_markdown(gather, diagnosis, verified=False)

    if args.skills_dir:
        cfg = SkillsConfig(
            skills_dir=Path(args.skills_dir).resolve(),
            db_path=Path(args.skills_dir).resolve() / ".index" / "skills.db",
            record_enabled=True,
            search_limit=3,
        )
    else:
        from skills.config import skills_config

        cfg = skills_config()

    store = SqliteFtsSkillStore(cfg)
    result = store.upsert_skill(markdown)
    print(json.dumps(dict(result), indent=2))
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
