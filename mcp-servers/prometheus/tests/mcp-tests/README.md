# MCP 云联调（Prometheus）

- **PowerShell 一键脚本**：`run_prometheus_mcp_test.ps1`（编辑其中的 `PROMETHEUS_BASE_URL` 等变量后，在仓库根 `powershell -File tests/mcp-tests/run_prometheus_mcp_test.ps1` 或从本目录运行）。
- **pytest integration**：在设置 `PROMETHEUS_BASE_URL` 或 `PROMETHEUS_E2E_BASE_URL` 后，从 `mcp-servers/prometheus` 执行：
  - `python -m pytest tests/mcp-tests -m integration -v`

未设置上述环境变量时，integration 用例会 **skip**，不连云。
