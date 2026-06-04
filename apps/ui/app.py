#!/usr/bin/env python3
"""Sentinel-X minimal Streamlit UI (W4): list pods, top CPU, inspect."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import streamlit as st

_INTEGRATION_SRC = Path(__file__).resolve().parents[2] / "agents" / "langgraph-integration" / "src"
if str(_INTEGRATION_SRC) not in sys.path:
    sys.path.insert(0, str(_INTEGRATION_SRC))

DEFAULTS = {
    "LANGGRAPH_API_URL": "http://127.0.0.1:2024",
    "CLUSTER_ID": "k3s-prod",
    "NAMESPACE": "kube-system",
}


def _resolve_thread_id(cluster_id: str, tenant_id: str = "") -> str:
    from models.scope import resolve_langgraph_thread_id

    return resolve_langgraph_thread_id(cluster_id=cluster_id, tenant_id=tenant_id or None)


def _default_thread_id() -> str:
    explicit = os.environ.get("LANGGRAPH_THREAD_ID", "").strip()
    if explicit and explicit.upper() != "AUTO":
        return explicit
    cluster_id = _env("CLUSTER_ID")
    if cluster_id:
        try:
            return _resolve_thread_id(cluster_id)
        except Exception:
            pass
    return ""


def _env(key: str) -> str:
    return os.environ.get(key, DEFAULTS.get(key, "")).strip()


def _live_enabled() -> bool:
    return os.environ.get("LANGGRAPH_RUN_LIVE", "").strip().lower() in ("1", "true", "yes")


def _format_bytes(value: Any) -> str:
    if value is None:
        return ""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    if n < 1024:
        return f"{n:.0f} B"
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        n /= 1024
        if n < 1024:
            return f"{n:.2f} {unit}"
    return f"{n:.2f} PiB"


def _pods_table_rows(pods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in pods:
        rows.append(
            {
                "name": p.get("name"),
                "namespace": p.get("namespace"),
                "phase": p.get("status"),
                "cpu_cores": p.get("cpu_cores"),
                "memory": _format_bytes(p.get("memory_bytes")),
            }
        )
    return rows


def _check_langgraph(api_url: str) -> tuple[bool, str]:
    if not api_url:
        return False, "Set LANGGRAPH_API_URL in the sidebar."
    if not _live_enabled():
        return False, "Set LANGGRAPH_RUN_LIVE=1 to query the live LangGraph server."
    os.environ["LANGGRAPH_API_URL"] = api_url
    try:
        from clients.langgraph_client import get_langgraph_client, verify_langgraph_connection

        client = get_langgraph_client()
        verify_langgraph_connection(client)
        return True, ""
    except Exception as exc:
        return False, f"LangGraph unreachable: {exc}"


def _run_query(op: str, thread_id: str, **params: Any) -> dict[str, Any]:
    from clients.langgraph_client import get_langgraph_client, query_sentinel

    client = get_langgraph_client()
    return query_sentinel(op, thread_id=thread_id, client=client, **params)


def _run_inspect(
    *,
    thread_id: str,
    cluster_id: str,
    namespace: str,
    pod_name: str,
) -> dict[str, Any]:
    from clients.langgraph_client import (
        get_inspect_outputs_from_stream,
        get_langgraph_client,
        stream_sentinel_run,
    )

    client = get_langgraph_client()
    payload: dict[str, object] = {
        "inspect": {
            "cluster_id": cluster_id,
            "namespace": namespace,
            "pod_name": pod_name,
            "dry_run": True,
        }
    }
    chunks = list(stream_sentinel_run(payload, client=client, thread_id=thread_id))
    return get_inspect_outputs_from_stream(chunks)


def _sidebar_config() -> dict[str, str]:
    st.sidebar.header("Connection")
    api_url = st.sidebar.text_input(
        "LANGGRAPH_API_URL",
        value=st.session_state.get("api_url", _env("LANGGRAPH_API_URL")),
    )
    thread_id = st.sidebar.text_input(
        "LANGGRAPH_THREAD_ID",
        value=st.session_state.get("thread_id", _default_thread_id()),
        help="Leave empty to derive from CLUSTER_ID (same as sync).",
    )
    cluster_id = st.sidebar.text_input(
        "CLUSTER_ID",
        value=st.session_state.get("cluster_id", _env("CLUSTER_ID")),
    )
    namespace = st.sidebar.text_input(
        "NAMESPACE",
        value=st.session_state.get("namespace", _env("NAMESPACE")),
    )
    if not thread_id.strip() and cluster_id.strip():
        try:
            thread_id = _resolve_thread_id(cluster_id)
        except Exception:
            pass
    st.session_state.update(
        api_url=api_url,
        thread_id=thread_id,
        cluster_id=cluster_id,
        namespace=namespace,
    )
    os.environ["LANGGRAPH_API_URL"] = api_url
    return {
        "api_url": api_url,
        "thread_id": thread_id,
        "cluster_id": cluster_id,
        "namespace": namespace,
    }


def main() -> None:
    st.set_page_config(page_title="Sentinel-X", layout="wide")
    st.title("Sentinel-X")
    st.caption("Live pod query and inspect (LangGraph thread checkpoint)")

    cfg = _sidebar_config()
    ok, err = _check_langgraph(cfg["api_url"])

    if not ok:
        st.warning(err)
        st.info(
            "Start LangGraph (`langgraph dev` or systemd), run K8s sync cron, then set "
            "`LANGGRAPH_RUN_LIVE=1`. Config: `docs/DEPLOY-REFERENCE.md`."
        )
        return

    if not cfg["thread_id"].strip():
        st.error("Set LANGGRAPH_THREAD_ID or CLUSTER_ID (see docs/DEPLOY-REFERENCE.md).")
        return

    st.success(f"Connected to {cfg['api_url']}")

    tab_pods, tab_cpu, tab_inspect = st.tabs(["Pods", "Top CPU", "Inspect"])

    with tab_pods:
        if st.button("Refresh pods", key="refresh_pods"):
            st.session_state.pop("pods_result", None)
        try:
            result = _run_query(
                "list_pods",
                cfg["thread_id"],
                cluster_id=cfg["cluster_id"],
                namespace=cfg["namespace"],
            )
            st.session_state["pods_result"] = result
        except Exception as exc:
            st.error(f"list_pods failed: {exc}")
            result = st.session_state.get("pods_result") or {}
        else:
            result = st.session_state.get("pods_result", result)

        pods = result.get("pods") or []
        st.write(f"**{result.get('count', len(pods))}** pods in `{cfg['namespace']}`")
        if pods:
            st.dataframe(_pods_table_rows(pods), width="stretch", hide_index=True)
            st.session_state["pod_names"] = [p.get("name") for p in pods if p.get("name")]
        else:
            st.info("No pods in graph. Run K8s sync or check cluster/namespace/thread_id.")

    with tab_cpu:
        if st.button("Refresh top CPU", key="refresh_cpu"):
            st.session_state.pop("cpu_result", None)
        try:
            cpu_result = _run_query(
                "top_pods_by_cpu",
                cfg["thread_id"],
                cluster_id=cfg["cluster_id"],
                namespace=cfg["namespace"],
                limit=10,
            )
            st.session_state["cpu_result"] = cpu_result
        except Exception as exc:
            st.error(f"top_pods_by_cpu failed: {exc}")
            cpu_result = st.session_state.get("cpu_result") or {}
        else:
            cpu_result = st.session_state.get("cpu_result", cpu_result)

        cpu_pods = cpu_result.get("pods") or []
        st.write(f"Top **{cpu_result.get('count', len(cpu_pods))}** by CPU")
        if cpu_pods:
            st.dataframe(_pods_table_rows(cpu_pods), width="stretch", hide_index=True)
        else:
            st.info("No CPU metrics on pods. Run Prom sync (W3) after K8s sync.")

    with tab_inspect:
        pod_names: list[str] = st.session_state.get("pod_names") or []
        if not pod_names:
            st.info("Load pods in the Pods tab first, or type a pod name below.")
        selected = st.selectbox("Pod", options=pod_names or [""], index=0 if pod_names else 0)
        manual = st.text_input("Or pod name", value=selected or "")
        pod_name = (manual or selected).strip()

        if st.button("Run inspect", disabled=not pod_name):
            with st.spinner(f"Inspecting {pod_name}…"):
                try:
                    outputs = _run_inspect(
                        thread_id=cfg["thread_id"],
                        cluster_id=cfg["cluster_id"],
                        namespace=cfg["namespace"],
                        pod_name=pod_name,
                    )
                    st.session_state["inspect_outputs"] = outputs
                except Exception as exc:
                    st.error(f"Inspect failed: {exc}")

        outputs = st.session_state.get("inspect_outputs") or {}
        if outputs:
            with st.expander("Diagnosis", expanded=True):
                st.json(outputs.get("diagnosis") or {})
            with st.expander("Narrative"):
                narrative = outputs.get("narrative") or {}
                summary = narrative.get("summary")
                if summary:
                    st.write(summary)
                md = narrative.get("markdown")
                if isinstance(md, str) and md.strip():
                    st.markdown(md)
                st.caption(f"narrative_source={narrative.get('narrative_source')}")
            with st.expander("Execution"):
                st.json(outputs.get("execution") or {})
            with st.expander("Gather (raw)"):
                st.json(outputs.get("gather") or {})


if __name__ == "__main__":
    main()
