#!/usr/bin/env python3
"""Capture Streamlit UI via local SSH tunnel using Playwright."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "demo" / "streamlit-ui.png"
URL = "http://127.0.0.1:8501"
SSH_HOST = "root@47.120.6.221"
TUNNEL = "8501:127.0.0.1:8501"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install: pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    ssh = subprocess.Popen(
        ["ssh", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes", "-N", "-L", TUNNEL, SSH_HOST],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(2)
        if ssh.poll() is not None:
            err = (ssh.stderr.read() or b"").decode()
            print(f"SSH tunnel failed: {err}", file=sys.stderr)
            return 1

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(URL, wait_until="networkidle", timeout=120_000)
            # Streamlit reruns; wait for main content
            page.wait_for_timeout(5000)
            try:
                page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=30_000)
            except Exception:
                pass
            OUT.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(OUT), full_page=False)
            browser.close()
        print(f"Wrote {OUT}")
        return 0
    finally:
        ssh.terminate()
        try:
            ssh.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ssh.kill()


if __name__ == "__main__":
    raise SystemExit(main())
