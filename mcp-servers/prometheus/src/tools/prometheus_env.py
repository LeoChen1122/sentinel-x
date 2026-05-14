from __future__ import annotations

import os


def verify_ssl_from_env() -> bool:
    """Return False when PROMETHEUS_VERIFY_SSL is a common falsy string."""
    raw = os.getenv("PROMETHEUS_VERIFY_SSL", "true").strip().lower()
    return raw not in ("0", "false", "no")
