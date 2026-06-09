"""Sandbox environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class SandboxConfig:
    enabled: bool
    namespace: str
    audit_dir: Path
    image: str
    timeout_sec: int
    max_replicas: int
    kubeconfig: Path
    ready_sec: int
    verify_poll_sec: int
    verify_timeout_sec: int
    payload_truncate: int


def sandbox_config() -> SandboxConfig:
    root = os.environ.get("SENTINEL_ROOT", "").strip()
    base = Path(root) if root else _repo_root()
    enabled_raw = os.environ.get("SENTINEL_SANDBOX_ENABLED", "1").strip().lower()
    enabled = enabled_raw not in ("0", "false", "no", "off")
    namespace = os.environ.get("SENTINEL_SANDBOX_NAMESPACE", "sentinel-sandbox").strip()
    audit_dir = Path(
        os.environ.get("SENTINEL_SANDBOX_AUDIT_DIR", str(base / "sandbox" / "audit"))
    ).resolve()
    image = os.environ.get("SENTINEL_SANDBOX_IMAGE", "sentinel-x-sandbox:latest").strip()
    try:
        timeout_sec = max(5, int(os.environ.get("SENTINEL_SANDBOX_TIMEOUT_SEC", "60")))
    except ValueError:
        timeout_sec = 60
    try:
        max_replicas = max(1, int(os.environ.get("SENTINEL_SANDBOX_MAX_REPLICAS", "5")))
    except ValueError:
        max_replicas = 5
    try:
        ready_sec = max(1, int(os.environ.get("SENTINEL_SANDBOX_READY_SEC", "30")))
    except ValueError:
        ready_sec = 30
    try:
        verify_poll_sec = max(1, int(os.environ.get("SENTINEL_SANDBOX_VERIFY_POLL_SEC", "5")))
    except ValueError:
        verify_poll_sec = 5
    try:
        verify_timeout_sec = max(
            ready_sec, int(os.environ.get("SENTINEL_SANDBOX_VERIFY_TIMEOUT_SEC", "120"))
        )
    except ValueError:
        verify_timeout_sec = 120
    try:
        payload_truncate = max(
            256, int(os.environ.get("SENTINEL_SANDBOX_PAYLOAD_TRUNCATE", "4096"))
        )
    except ValueError:
        payload_truncate = 4096
    kube = (
        os.environ.get("KUBECONFIG", "").strip()
        or os.environ.get("KUBECONFIG_TARGET", "").strip()
        or os.environ.get("K3S_KUBECONFIG", "").strip()
        or str(Path.home() / ".kube" / "config")
    )
    return SandboxConfig(
        enabled=enabled,
        namespace=namespace,
        audit_dir=audit_dir,
        image=image,
        timeout_sec=timeout_sec,
        max_replicas=max_replicas,
        kubeconfig=Path(kube).resolve(),
        ready_sec=ready_sec,
        verify_poll_sec=verify_poll_sec,
        verify_timeout_sec=verify_timeout_sec,
        payload_truncate=payload_truncate,
    )
