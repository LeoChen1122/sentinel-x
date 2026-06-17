# Demo assets / Demo 素材

Screenshots for the root [README.md](../../README.md) Demo section.

| File | Content | 内容 |
|------|---------|------|
| `inspect-crashloop.png` | API inspect → `issues: CrashLoop` → `restart_pod` (simulated) | Agent 根因分析 |
| `streamlit-ui.png` | Streamlit layout: pods table + inspect (representative) | UI 界面示意 |
| `sandbox-verify.png` | `sandbox_demo.py` dry-run execution output | 沙箱预演 |

## Regenerate | 重新生成

**1. Capture live outputs on server** (optional refresh):

```bash
bash scripts/capture-demo-outputs.sh   # on production host as root
# copies to docs/assets/demo/ via scp — see script header
```

**2. Render PNGs** (local, requires Pillow):

```bash
pip install Pillow
python scripts/render_demo_screenshots.py
```

`inspect-crashloop.png` and `sandbox-verify.png` use **live** data from `47.120.6.221` (2026-06-17).  
`streamlit-ui.png` is a **styled snapshot** (UI query failed in headless capture; layout matches `apps/ui/app.py`).

## Manual screenshot (preferred for Streamlit)

```bash
ssh -L 8501:127.0.0.1:8501 root@<host>
# browser → http://127.0.0.1:8501 → save as streamlit-ui.png
```

Replace `streamlit-ui.png` when you have a real browser capture.
