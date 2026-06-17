#!/usr/bin/env python3
"""Normalize demo PNGs to a common canvas size for README display."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "docs" / "assets" / "demo"
TARGET_W, TARGET_H = 1400, 900
BG = (18, 22, 28)
FILES = ("inspect-crashloop.png", "streamlit-ui.png", "sandbox-verify.png")


def fit_canvas(src: Path, dst: Path) -> None:
    im = Image.open(src).convert("RGB")
    scale = min(TARGET_W / im.width, TARGET_H / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), BG)
    ox = (TARGET_W - nw) // 2
    oy = (TARGET_H - nh) // 2
    canvas.paste(resized, (ox, oy))
    canvas.save(dst, optimize=True)
    print(f"{src.name}: {im.size} -> {TARGET_W}x{TARGET_H}")


def main() -> None:
    for name in FILES:
        path = DEMO / name
        if not path.exists():
            raise SystemExit(f"missing {path}")
        fit_canvas(path, path)


if __name__ == "__main__":
    main()
