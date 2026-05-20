"""Optional LLM polish for inspection narratives (Qwen via DashScope compatible API)."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from typing import Any

from agent.types import DiagnosisReport, GatherResult, InspectionReport

logger = logging.getLogger(__name__)

# Alibaba Cloud Model Studio / 百炼 OpenAI-compatible endpoint (official sample).
DEFAULT_LLM_MODEL = "qwen3.6-plus"
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Tests patch this to avoid real API calls.
call_openai: Callable[[list[dict[str, str]]], str] | None = None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _api_key() -> str | None:
    for name in (
        "DASHSCOPE_API_KEY",
        "OPENAI_API_KEY",
        "LANGCHAIN_API_KEY",
        "LANGSMITH_API_KEY",
    ):
        v = os.getenv(name, "").strip()
        if v:
            return v
    return None


def _base_url() -> str | None:
    raw = os.getenv("OPENAI_BASE_URL", "").strip()
    return raw.rstrip("/") if raw else None


def _default_model() -> str:
    return os.getenv("SENTINEL_LLM_MODEL", DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL


def _timeout_sec() -> float:
    raw = os.getenv("SENTINEL_LLM_TIMEOUT_SEC", "60").strip() or "60"
    try:
        t = float(raw)
    except ValueError:
        return 60.0
    return t if t > 0 else 60.0


def _narrative_mode() -> str:
    return os.getenv("SENTINEL_NARRATIVE_LLM_MODE", "polish").strip().lower() or "polish"


def _thinking_enabled() -> bool:
    return _env_bool("SENTINEL_LLM_ENABLE_THINKING", False)


def llm_enabled() -> bool:
    """True when LLM polish is allowed and an API key is configured."""
    return _env_bool("SENTINEL_LLM_ENABLED", False) and _api_key() is not None


def resolve_use_llm(explicit: bool | None) -> bool:
    """Map ``use_llm`` tri-state: False / True / None (follow env when None)."""
    if explicit is False:
        return False
    if explicit is True:
        return True
    return llm_enabled()


def llm_narrative_config() -> dict[str, Any]:
    """Runtime LLM settings for demos and logging (no secrets)."""
    base = _base_url()
    thinking = _thinking_enabled()
    return {
        "enabled": llm_enabled(),
        "provider": "dashscope_compatible",
        "model": _default_model(),
        "timeout_sec": _timeout_sec(),
        "base_url": base or DEFAULT_DASHSCOPE_BASE_URL,
        "base_url_configured": bool(base),
        "api_key_set": _api_key() is not None,
        "mode": _narrative_mode(),
        "enable_thinking": thinking,
        "stream": thinking,
    }


def _make_client() -> Any:
    """OpenAI client configured like the official DashScope sample."""
    from openai import OpenAI

    api_key = _api_key()
    if not api_key:
        raise ValueError("LLM API key not configured (set DASHSCOPE_API_KEY)")
    return OpenAI(
        api_key=api_key,
        base_url=_base_url() or DEFAULT_DASHSCOPE_BASE_URL,
        timeout=_timeout_sec(),
    )


def _build_messages(
    report: InspectionReport,
    gather: GatherResult,
    *,
    diagnosis: DiagnosisReport | None = None,
) -> list[dict[str, str]]:
    facts: dict[str, Any] = {
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
    if diagnosis is not None:
        facts["diagnosis"] = {
            "issues": diagnosis.get("issues", []),
            "recommended_actions": diagnosis.get("recommended_actions", []),
            "severity": diagnosis.get("severity"),
            "diagnosis_source": diagnosis.get("diagnosis_source"),
        }
    system = (
        "You are a Kubernetes inspection assistant. "
        "Rewrite the inspection report using ONLY the JSON facts provided. "
        "You must preserve every entity_id exactly as given (pod:, event:, inspection: prefixes). "
        "Do not invent pods, events, or inspections. "
        "Do not change the diagnosis issues or recommended_actions lists; you may reference them in prose. "
        "If diagnosis is present, add a ## Recommended actions section summarizing recommended_actions. "
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


def _completion_sync(client: Any, messages: list[dict[str, str]]) -> str:
    """Non-stream JSON completion (default pipeline path)."""
    try:
        resp = client.chat.completions.create(
            model=_default_model(),
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
            stream=False,
        )
    except Exception:
        resp = client.chat.completions.create(
            model=_default_model(),
            messages=messages,
            temperature=0.2,
            stream=False,
        )
    content = resp.choices[0].message.content
    if not content:
        raise ValueError("empty LLM response")
    return content


def _completion_stream_thinking(client: Any, messages: list[dict[str, str]]) -> str:
    """Stream with ``enable_thinking``; only final ``content`` is returned."""
    stream = client.chat.completions.create(
        model=_default_model(),
        messages=messages,
        temperature=0.2,
        stream=True,
        extra_body={"enable_thinking": True},
    )
    content_parts: list[str] = []
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            logger.debug("LLM reasoning chunk: %s", reasoning)
        if delta.content:
            content_parts.append(delta.content)
    content = "".join(content_parts)
    if not content:
        raise ValueError("empty LLM stream response")
    return content


def _invoke_openai(messages: list[dict[str, str]]) -> str:
    if call_openai is not None:
        return call_openai(messages)

    client = _make_client()
    if _thinking_enabled():
        return _completion_stream_thinking(client, messages)
    return _completion_sync(client, messages)


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


def _is_timeout_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if "Timeout" in name or "timeout" in str(exc).lower():
        return True
    cause = getattr(exc, "__cause__", None)
    return cause is not None and _is_timeout_error(cause)


def polish_inspection_report(
    report: InspectionReport,
    gather: GatherResult,
    *,
    diagnosis: DiagnosisReport | None = None,
) -> InspectionReport:
    """Polish ``markdown`` and ``summary`` via LLM; keep linked_* from template."""
    timeout_sec = _timeout_sec()
    try:
        raw = _invoke_openai(_build_messages(report, gather, diagnosis=diagnosis))
        summary, markdown = _parse_polish_response(raw)
    except Exception as e:
        is_timeout = _is_timeout_error(e)
        logger.warning(
            "LLM polish failed (%s, timeout=%ss), using template: %s",
            "timeout" if is_timeout else "error",
            timeout_sec,
            e,
        )
        out = dict(report)
        out["narrative_source"] = "template"
        out["llm_error"] = str(e)
        out.setdefault("ok", True)
        return InspectionReport(**out)

    out = dict(report)
    out["summary"] = summary
    out["markdown"] = markdown
    out["narrative_source"] = "llm"
    out["llm_error"] = None
    out.setdefault("ok", True)
    return InspectionReport(**out)
