"""Mock tenant registry for phase C ACL (4-0b may replace with live config)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_DEFAULT_TENANTS: dict[str, dict[str, list[str]]] = {
    "team-alpha": {"clusters": ["dev-cluster"]},
    "team-beta": {"clusters": ["dev-cluster", "prod-cluster"]},
}

_REGISTRY_CACHE: dict[str, dict[str, list[str]]] | None = None


class TenantAccessError(ValueError):
    """Tenant is not allowed to access the requested cluster."""


def _package_configs_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "configs"


def _parse_yaml_tenants(data: Any) -> dict[str, dict[str, list[str]]]:
    if not isinstance(data, dict):
        return {}
    rows = data.get("tenants")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, list[str]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        tid = row.get("id")
        clusters = row.get("clusters")
        if tid is None or not str(tid).strip():
            continue
        if not isinstance(clusters, list):
            continue
        out[str(tid).strip()] = {
            "clusters": [str(c).strip() for c in clusters if c is not None and str(c).strip()]
        }
    return out


def load_tenant_registry(*, reload: bool = False) -> dict[str, dict[str, list[str]]]:
    """Load tenant → allowed clusters from YAML or built-in defaults."""
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is not None and not reload:
        return _REGISTRY_CACHE

    registry = {k: dict(v) for k, v in _DEFAULT_TENANTS.items()}
    configs = _package_configs_dir()
    for name in ("tenants.yaml", "tenants.yml"):
        path = configs / name
        if not path.is_file():
            continue
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            break
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        loaded = _parse_yaml_tenants(parsed)
        if loaded:
            registry = loaded
        break

    _REGISTRY_CACHE = registry
    return registry


def list_tenants() -> list[str]:
    return sorted(load_tenant_registry().keys())


def allowed_clusters(tenant_id: str) -> list[str]:
    tid = str(tenant_id).strip()
    reg = load_tenant_registry()
    if tid not in reg:
        raise TenantAccessError(f"unknown tenant: {tid}")
    return list(reg[tid].get("clusters") or [])


def assert_tenant_cluster_access(tenant_id: str, cluster_id: str) -> None:
    """Raise ``TenantAccessError`` if tenant cannot access cluster."""
    tid = str(tenant_id).strip()
    cid = str(cluster_id).strip()
    if not tid:
        raise TenantAccessError("tenant_id is required")
    if not cid:
        raise TenantAccessError("cluster_id is required")
    allowed = allowed_clusters(tid)
    if cid not in allowed:
        raise TenantAccessError(
            f"tenant {tid!r} cannot access cluster {cid!r} (allowed: {allowed})"
        )
