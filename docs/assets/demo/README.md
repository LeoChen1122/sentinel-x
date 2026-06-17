# Demo assets / Demo 素材

Screenshots for the root [README.md](../../README.md) Demo section.

All demo PNGs are normalized to **1400×900** for consistent README display.

| File | Content | 内容 |
|------|---------|------|
| `inspect-crashloop.png` | API inspect → `issues: CrashLoop` → `restart_pod` (simulated) | Agent 根因分析 |
| `streamlit-ui.png` | Streamlit `:8501` live capture via SSH tunnel | UI 真实截图 |
| `sandbox-verify.png` | `sandbox_demo.py` dry-run execution output | 沙箱预演 |

## Regenerate | 重新生成

**1. Capture live outputs on server:**

```bash
bash scripts/capture-demo-outputs.sh   # on production host as root
# scp inspect.json + sandbox.txt to docs/assets/demo/
```

**2. Render inspect + sandbox PNGs** (1400×900, requires Pillow + source files in `docs/assets/demo/`):

```bash
pip install Pillow
python scripts/render_demo_screenshots.py
```

**3. Streamlit browser capture** (1400×900 viewport):

```bash
pip install playwright && playwright install chromium
python scripts/capture_streamlit_screenshot.py
```

**4. Normalize all three to same canvas** (if sizes drift):

```bash
python scripts/normalize_demo_images.py
```

README uses `<img width="1000">` per screenshot (full-width stack, not 3-column table).
