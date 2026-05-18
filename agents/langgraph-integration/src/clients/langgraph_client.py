"""Thin sync client for the LangGraph HTTP API (``langgraph-sdk``).

Some internal docs still show ``from langgraph import LangGraphClient`` with ``host=``.
The supported Python package is ``langgraph-sdk``; use ``get_sync_client(url=..., ...)``
(``url``, not ``host``). See: https://reference.langchain.com/python/langgraph-sdk/client/
"""

from __future__ import annotations

import os
from typing import Any

from langgraph_sdk import get_sync_client
from langgraph_sdk.client import SyncLangGraphClient


def _nonempty_env(var: str | None) -> str | None:
    return var.strip() if var and var.strip() else None


def _langgraph_base_url() -> str:
    url = _nonempty_env(os.getenv("LANGGRAPH_API_URL")) or _nonempty_env(
        os.getenv("LANGGRAPH_URL")
    )
    if not url:
        raise ValueError(
            "Set LANGGRAPH_API_URL (or LANGGRAPH_URL) to the LangGraph API base URL "
            "(e.g. https://your-deployment.langgraph.cloud)"
        )
    return url.rstrip("/")


def _api_key_from_env() -> str | None:
    for name in ("LANGGRAPH_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"):
        v = _nonempty_env(os.getenv(name))
        if v:
            return v
    return None


def _request_timeout() -> float:
    raw = os.getenv("LANGGRAPH_REQUEST_TIMEOUT", "30").strip() or "30"
    try:
        t = float(raw)
    except ValueError:
        return 30.0
    return t if t > 0 else 30.0


def get_langgraph_sync_client() -> SyncLangGraphClient:
    """Return a :class:`SyncLangGraphClient` from environment configuration."""
    url = _langgraph_base_url()
    timeout = _request_timeout()
    api_key = _api_key_from_env()
    kwargs: dict[str, Any] = {"url": url, "timeout": timeout}
    if api_key is not None:
        kwargs["api_key"] = api_key
    return get_sync_client(**kwargs)


def verify_langgraph_connection(client: SyncLangGraphClient) -> dict[str, Any]:
    """Perform a lightweight read against the API to confirm connectivity."""
    client.assistants.search(limit=1)
    return {"ok": True, "assistants_checked": True}


# Graph ID in langgraph-server/langgraph.json → graphs.sentinel
DEFAULT_GRAPH_ID = "sentinel"


def get_langgraph_client() -> SyncLangGraphClient:
    """Alias for :func:`get_langgraph_sync_client` (Sentinel-X guide naming)."""
    return get_langgraph_sync_client()


def stream_sentinel_run(
    payload: dict[str, Any],
    *,
    graph_id: str = DEFAULT_GRAPH_ID,
    client: SyncLangGraphClient | None = None,
    stream_mode: str = "values",
    thread_id: str | None = None,
):
    """Stream one run against the local ``sentinel`` graph (step 8 smoke).

    Yields SDK stream chunks. Requires ``langgraph dev`` (or ``up``) and
    ``LANGGRAPH_API_URL`` pointing at that server.

    Pass ``thread_id`` to accumulate graph state across sync/query runs on the
    same LangGraph thread checkpoint.
    """
    c = client or get_langgraph_sync_client()
    return c.runs.stream(
        thread_id,
        graph_id,
        input={"payload": payload},
        stream_mode=stream_mode,
    )


def _chunk_data(chunk: Any) -> Any:
    return getattr(chunk, "data", chunk)


def get_payload_from_stream(chunks: list[Any]) -> dict[str, Any]:
    """Return the last stream values payload that contains graph data."""
    payload: dict[str, Any] = {}
    for chunk in chunks:
        data = _chunk_data(chunk)
        if not isinstance(data, dict):
            continue
        candidate = data.get("payload") if isinstance(data.get("payload"), dict) else data
        if not isinstance(candidate, dict):
            continue
        if candidate.get("entities") is not None or candidate.get("query_result") is not None:
            payload = candidate
    return payload


def query_sentinel(
    op: str,
    *,
    thread_id: str,
    client: SyncLangGraphClient | None = None,
    graph_id: str = DEFAULT_GRAPH_ID,
    **params: Any,
) -> dict[str, Any]:
    """Run a graph query op on a thread and return ``query_result``."""
    payload = {"query": {"op": op, **params}}
    chunks = list(
        stream_sentinel_run(
            payload,
            thread_id=thread_id,
            client=client,
            graph_id=graph_id,
        )
    )
    final = get_payload_from_stream(chunks)
    result = final.get("query_result")
    return result if isinstance(result, dict) else {}
