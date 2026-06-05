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


def _is_not_found_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if "NotFound" in name:
        return True
    msg = str(exc).lower()
    return "not found" in msg or "notfound" in msg


def _thread_id_from_response(thread: Any, fallback: str) -> str:
    if isinstance(thread, dict):
        raw = thread.get("thread_id") or thread.get("id")
        return str(raw) if raw else fallback
    raw = getattr(thread, "thread_id", None) or getattr(thread, "id", None)
    return str(raw) if raw else fallback


def ensure_langgraph_thread(
    client: SyncLangGraphClient,
    thread_id: str | None,
) -> str | None:
    """Ensure ``thread_id`` exists on the LangGraph server before ``runs.stream``.

    UUID5 mapping alone does not register a thread; this calls ``threads.create``
    when ``threads.get`` returns not-found. ``thread_id=None`` leaves stateless runs
    to the server.
    """
    if thread_id is None:
        return None
    tid = str(thread_id).strip()
    if not tid:
        return None
    try:
        client.threads.get(tid)
        return tid
    except Exception as exc:
        if not _is_not_found_error(exc):
            raise
    create_kwargs: dict[str, Any] = {"thread_id": tid}
    try:
        created = client.threads.create(**create_kwargs, if_exists="do_nothing")
    except TypeError:
        created = client.threads.create(**create_kwargs)
    return _thread_id_from_response(created, tid)


def find_sentinel_graph(client: SyncLangGraphClient) -> dict[str, Any] | None:
    """Return first assistant row whose graph id matches :data:`DEFAULT_GRAPH_ID`."""
    try:
        rows = client.assistants.search(graph_id=DEFAULT_GRAPH_ID, limit=5)
    except TypeError:
        rows = client.assistants.search(limit=20)
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        gid = row.get("graph_id") or row.get("assistant_id")
        if gid == DEFAULT_GRAPH_ID:
            return row
    return rows[0] if rows else None


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
    same LangGraph thread checkpoint. The thread is created on the server when
    missing (see :func:`ensure_langgraph_thread`).
    """
    c = client or get_langgraph_sync_client()
    tid = ensure_langgraph_thread(c, thread_id)
    return c.runs.stream(
        tid,
        graph_id,
        input={"payload": payload},
        stream_mode=stream_mode,
    )


def _chunk_data(chunk: Any) -> Any:
    return getattr(chunk, "data", chunk)


_INSPECT_OUTPUT_KEYS = frozenset({
    "gather",
    "narrative",
    "diagnosis",
    "execution",
    "skill_matches",
    "skill_record",
    "skill_verification",
})


def _payload_from_chunk_data(data: dict[str, Any]) -> dict[str, Any] | None:
    candidate = data.get("payload") if isinstance(data.get("payload"), dict) else data
    return candidate if isinstance(candidate, dict) else None


def get_payload_from_stream(chunks: list[Any]) -> dict[str, Any]:
    """Return the last stream values payload that contains graph data."""
    payload: dict[str, Any] = {}
    for chunk in chunks:
        data = _chunk_data(chunk)
        if not isinstance(data, dict):
            continue
        candidate = _payload_from_chunk_data(data)
        if not candidate:
            continue
        if candidate.get("entities") is not None or candidate.get("query_result") is not None:
            payload = candidate
    return payload


def get_inspect_outputs_from_stream(chunks: list[Any]) -> dict[str, Any]:
    """Return inspect pipeline fields from the last stream chunk that has any of them.

    Keys: ``gather``, ``narrative``, ``diagnosis``, ``execution`` (subset present).
    Does not alter :func:`get_payload_from_stream` query/sync semantics.
    """
    merged: dict[str, Any] = {}
    last_payload: dict[str, Any] = {}
    for chunk in chunks:
        data = _chunk_data(chunk)
        if not isinstance(data, dict):
            continue
        candidate = _payload_from_chunk_data(data)
        if not candidate:
            continue
        if _INSPECT_OUTPUT_KEYS.intersection(candidate.keys()):
            last_payload = candidate
    if not last_payload:
        return merged
    for key in _INSPECT_OUTPUT_KEYS:
        val = last_payload.get(key)
        if val is not None:
            merged[key] = val
    return merged


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
