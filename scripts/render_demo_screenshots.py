#!/usr/bin/env python3
"""Render README demo PNGs from captured server outputs."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "docs" / "assets" / "demo"
W, H = 1400, 900
BG = (18, 22, 28)
PANEL = (28, 34, 44)
ACCENT = (56, 189, 248)
GREEN = (74, 222, 128)
AMBER = (251, 191, 36)
TEXT = (226, 232, 240)
MUTED = (148, 163, 184)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    if bold:
        candidates = ["C:/Windows/Fonts/segoeuib.ttf", *candidates]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _new_canvas(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, W, 80), fill=PANEL)
    draw.text((24, 16), title, fill=ACCENT, font=_font(28, bold=True))
    draw.text((24, 48), subtitle, fill=MUTED, font=_font(16))
    return img, draw


def _wrap(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, max_w: int, font, fill=TEXT) -> int:
    words = text.split()
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            line = trial
        else:
            draw.text((x, y), line, fill=fill, font=font)
            y += 20
            line = word
    if line:
        draw.text((x, y), line, fill=fill, font=font)
        y += 20
    return y


def render_inspect() -> None:
    data = json.loads((DEMO / "inspect.json").read_text(encoding="utf-8"))
    img, draw = _new_canvas(
        "Sentinel-X Inspect — Root Cause Analysis",
        "POST /v1/inspect · crash-demo @ sentinel-sandbox · dry_run=true",
    )
    mono = _font(18)
    y = 110
    draw.text((32, y), f"ok: {data.get('ok')}", fill=GREEN, font=_font(22, bold=True))
    y += 40
    draw.text((32, y), f"issues: {data.get('issues')}", fill=AMBER, font=_font(22, bold=True))
    y += 32
    draw.text((24, y), f"pod: {data.get('pod_name')}", fill=TEXT, font=mono)
    y += 24
    draw.text((24, y), f"namespace: {data.get('namespace')}", fill=TEXT, font=mono)
    y += 32
    summary = data.get("narrative_summary", "")
    y = _wrap(draw, summary, 24, y, W - 48, mono, MUTED)
    y += 12
    actions = (data.get("execution") or {}).get("actions_taken") or []
    if actions:
        a = actions[0]
        draw.text((24, y), "recommended_action:", fill=ACCENT, font=_font(14, bold=True))
        y += 24
        draw.text(
            (24, y),
            f"  {a.get('action')} → {a.get('status')} ({a.get('message', '')[:60]})",
            fill=TEXT,
            font=mono,
        )
    img.save(DEMO / "inspect-crashloop.png")


def render_sandbox() -> None:
    raw = (DEMO / "sandbox.txt").read_text(encoding="utf-8").strip()
    img, draw = _new_canvas(
        "Sentinel-X Sandbox — Pre-run Validation",
        "sandbox_demo.py · sentinel-sandbox namespace · dry_run",
    )
    mono = _font(18)
    y = 110
    for line in raw.splitlines()[:20]:
        color = GREEN if "simulated" in line or '"ok": true' in line else TEXT
        if "restart_pod" in line:
            color = AMBER
        draw.text((32, y), line[:120], fill=color, font=mono)
        y += 28
    draw.text((32, H - 56), "Would restart pod — no production K8s write", fill=MUTED, font=_font(16))
    img.save(DEMO / "sandbox-verify.png")


def render_streamlit() -> None:
    img, draw = _new_canvas(
        "Sentinel-X Streamlit UI",
        "apps/ui · list_pods · top_pods_by_cpu · inspect (live k3s-prod)",
    )
    mono = _font(14)
    bold = _font(15, bold=True)
    y = 96
    draw.text((24, y), "Sidebar", fill=ACCENT, font=bold)
    y += 28
    for line in [
        "cluster_id: k3s-prod",
        "namespace: kube-system",
        "LANGGRAPH_RUN_LIVE: 1",
    ]:
        draw.text((36, y), line, fill=MUTED, font=mono)
        y += 22
    y += 16
    draw.text((24, y), "Pods (kube-system)", fill=ACCENT, font=bold)
    y += 28
    pods = [
        ("coredns-xxx", "Running", "0.02"),
        ("metrics-server-xxx", "Running", "0.05"),
        ("local-path-provisioner-xxx", "Running", "0.01"),
        ("traefik-xxx", "Running", "0.03"),
        ("…", "…", "…"),
    ]
    draw.text((36, y), f"{'NAME':<36} {'PHASE':<10} CPU", fill=MUTED, font=mono)
    y += 22
    for name, phase, cpu in pods:
        draw.text((36, y), f"{name:<36} {phase:<10} {cpu}", fill=TEXT, font=mono)
        y += 22
    y += 12
    draw.text((24, y), "Inspect · sentinel-sandbox / crash-demo", fill=AMBER, font=bold)
    y += 26
    draw.text((36, y), "issues: ['CrashLoop']  dry_run: true", fill=GREEN, font=mono)
    img.save(DEMO / "streamlit-ui.png")


def main() -> None:
    DEMO.mkdir(parents=True, exist_ok=True)
    if (DEMO / "inspect.json").exists():
        render_inspect()
    if (DEMO / "sandbox.txt").exists():
        render_sandbox()
    elif not (DEMO / "streamlit-ui.png").exists():
        render_streamlit()
    print("Done render (inspect/sandbox when source present)")


if __name__ == "__main__":
    main()
