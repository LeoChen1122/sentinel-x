#!/usr/bin/env python3
"""Smoke-test DashScope OpenAI-compatible API (official Qwen sample alignment)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent.llm import (  # noqa: E402
    DEFAULT_DASHSCOPE_BASE_URL,
    DEFAULT_LLM_MODEL,
    llm_narrative_config,
)


def _run_ping() -> int:
    from openai import OpenAI

    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        print("Set DASHSCOPE_API_KEY", file=sys.stderr)
        return 1
    base = os.getenv("OPENAI_BASE_URL", DEFAULT_DASHSCOPE_BASE_URL).strip()
    model = os.getenv("SENTINEL_LLM_MODEL", DEFAULT_LLM_MODEL).strip()
    client = OpenAI(api_key=api_key, base_url=base)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with one word: ok"}],
        stream=False,
    )
    text = (resp.choices[0].message.content or "").strip()
    print(f"model={model}")
    print(f"base_url={base}")
    print(f"reply={text}")
    return 0 if text else 1


def _run_thinking_demo() -> int:
    """Mirror official sample: stream + enable_thinking."""
    from openai import OpenAI

    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        print("Set DASHSCOPE_API_KEY", file=sys.stderr)
        return 1
    base = os.getenv("OPENAI_BASE_URL", DEFAULT_DASHSCOPE_BASE_URL).strip()
    model = os.getenv("SENTINEL_LLM_MODEL", DEFAULT_LLM_MODEL).strip()
    client = OpenAI(api_key=api_key, base_url=base)
    messages = [{"role": "user", "content": "你是谁"}]
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        extra_body={"enable_thinking": True},
        stream=True,
    )
    is_answering = False
    print("\n" + "=" * 20 + "思考过程" + "=" * 20)
    for chunk in completion:
        delta = chunk.choices[0].delta
        if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
            if not is_answering:
                print(delta.reasoning_content, end="", flush=True)
        if hasattr(delta, "content") and delta.content:
            if not is_answering:
                print("\n" + "=" * 20 + "完整回复" + "=" * 20)
                is_answering = True
            print(delta.content, end="", flush=True)
    print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="DashScope / Qwen connectivity smoke test")
    parser.add_argument(
        "--thinking",
        action="store_true",
        help="Run official stream + enable_thinking demo (not used by Agent pipeline)",
    )
    args = parser.parse_args()

    print("=== llm_narrative_config ===")
    print(json.dumps(llm_narrative_config(), indent=2, ensure_ascii=False))

    if args.thinking:
        return _run_thinking_demo()
    return _run_ping()


if __name__ == "__main__":
    raise SystemExit(main())
