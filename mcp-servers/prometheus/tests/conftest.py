"""Put ``src`` on sys.path so ``tools.*`` imports work in tests."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_SRC))
