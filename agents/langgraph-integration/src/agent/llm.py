"""Optional OpenAI polish for inspection narratives (phase B)."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from typing import Any

from agent.types import GatherResult, InspectionReport

logger = logging.getLogger(__name__)

# Tests patch this to avoid real API calls.
call_openai: Callable[[list[dict[str, str]]], str] | None = None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _api_key() -> str | None:
    for name in ("OPENAI_API_KEY", "LANGCHAIN_API_KEY", "LANGSMITH_API_KEY"):
        v = os.getenv(name, "").strip()
        if v:
            return v
    return None


def llm_enabled() -> bool:
    """True when LLM polish is allowed and an API key is configured."""
    return _env_bool("SENTINEL_LLM_ENABLED", False) and _api_key() is not None


def _default_model() -> str:
    return os.getenv("SENTINEL_LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def _timeout_sec() -> float:
    raw = os.getenv("SENTINEL_LLM_TIMEOUT_SEC", "30").strip() or "30"
    try:
        t = float(raw)
    except ValueError:
        return 30.0
    return t if t > 0 else 30.0


def _build_messages(report: InspectionReport, gather: GatherResult) -> list[dict[str, str]]:
    facts = {
        "cluster_id": gather["cluster_id"],
        "namespace": gather["namespace"],
        "pod_name": gather["pod_name"],
        "pod_entity_id": gather["pod_entity_id"],
        "queries": gather["queries"],
        "linked_events": report.get("linked_events", []),
        "linked_pods": report.get("linked_pods", []),
        "linked_inspections": report.get("linked_inspections", []),
        "template_sections": report.get("sections", []),
        "template_summary": report.get("summary", ""),
    }
    system = (
        "You are a Kubernetes inspection assistant. "
        "Rewrite the inspection report using ONLY the JSON facts provided. "
        "You must preserve every entity_id exactly as given (pod:, event:, inspection: prefixes). "
        "Do not invent pods, events, or inspections. "
        "Respond with a single JSON object: "
        '{"summary": "one paragraph", "markdown": "full markdown report with ## headings"}.'
    )
    user = (
        "Facts JSON:\n"
        f"{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
        "Template markdown for reference:\n"
        f"{report.get('markdown', '')}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _invoke_openai(messages: list[dict[str, str]]) -> str:
    if call_openai is not None:
        return call_openai(messages)

    from openai import OpenAI

    kwargs: dict[str, Any] = {"api_key": _api_key(), "timeout": _timeout_sec()}
    base = os.getenv("OPENAI_BASE_URL", "").strip()
    if base:
        kwargs["base_url"] = base.rstrip("/")
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=_default_model(),
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = resp.choices[0].message.content
    if not content:
        raise ValueError("empty LLM response")
    return content


def _parse_polish_response(raw: str) -> tuple[str, str]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    summary = str(data.get("summary", "")).strip()
    markdown = str(data.get("markdown", "")).strip()
    if not summary or not markdown:
        raise ValueError("LLM JSON missing summary or markdown")
    if not markdown.endswith("\n"):
        markdown += "\n"
    return summary, markdown


def polish_inspection_report(
    report: InspectionReport,
    gather: GatherResult,
) -> InspectionReport:
    """Polish ``markdown`` and ``summary`` via OpenAI; keep linked_* from template."""
    try:
        raw = _invoke_openai(_build_messages(report, gather))
        summary, markdown = _parse_polish_response(raw)
    except Exception as e:
        logger.warning("LLM polish failed, using template report: %s", e)
        out = dict(report)
        out.setdefault("narrative_source", "template")
        return InspectionReport(**out)

    out = dict(report)
    out["summary"] = summary
    out["markdown"] = markdown
    out["narrative_source"] = "llm"
    return InspectionReport(**out)
