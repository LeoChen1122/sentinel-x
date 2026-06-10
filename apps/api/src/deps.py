"""Shared dependencies for Sentinel-X API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import Header, HTTPException


def _ensure_integration_path() -> None:
    root = os.environ.get("SENTINEL_ROOT", "").strip()
    if root:
        integration_src = Path(root) / "agents" / "langgraph-integration" / "src"
    else:
        integration_src = Path(__file__).resolve().parents[3] / "agents" / "langgraph-integration" / "src"
    p = str(integration_src.resolve())
    if p not in sys.path:
        sys.path.insert(0, p)


_ensure_integration_path()


def verify_api_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("SENTINEL_API_TOKEN", "").strip()
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="invalid token")
