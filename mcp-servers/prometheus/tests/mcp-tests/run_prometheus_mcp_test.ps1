# =========================================
# File: tests/mcp-tests/run_prometheus_mcp_test.ps1
# Description: 云 Prometheus 联调：prom_query("up") + prom_query_range("up", 1h, step)
# Usage: 从任意目录执行： powershell -File <repo>\tests\mcp-tests\run_prometheus_mcp_test.ps1
# =========================================

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$srcPath = (Join-Path $repoRoot 'src').Replace('\', '/')

# ------------------------------
# 1. 配置云服务器 Prometheus
# ------------------------------
$env:PROMETHEUS_BASE_URL = "http://120.77.176.17:9090"
$env:PROMETHEUS_E2E_BASE_URL = $env:PROMETHEUS_BASE_URL
$env:PROMETHEUS_BEARER_TOKEN = ""
$env:PROMETHEUS_VERIFY_SSL = "false"

Write-Host "repoRoot=$repoRoot"
Write-Host "PROMETHEUS_BASE_URL=$env:PROMETHEUS_BASE_URL"
Write-Host "PROMETHEUS_E2E_BASE_URL=$env:PROMETHEUS_E2E_BASE_URL"
Write-Host "PROMETHEUS_VERIFY_SSL=$env:PROMETHEUS_VERIFY_SSL"

# ------------------------------
# 2. 激活虚拟环境
# ------------------------------
$venvPath = Join-Path $repoRoot '.venv\Scripts\Activate.ps1'

if (Test-Path $venvPath) {
    Write-Host "Activating virtual environment..."
    & $venvPath
} else {
    Write-Error "虚拟环境激活脚本不存在：$venvPath"
    exit 1
}

# 说明：直连 tools（非 MCP stdio）。测 MCP：使用 repoRoot 下 .venv\Scripts\python.exe src\server.py

# ------------------------------
# 3. 测试 prom_query（单行 python -c）
# ------------------------------
$pyexe = Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
if (-Not (Test-Path $pyexe)) {
    Write-Error "找不到解释器：$pyexe"
    exit 1
}

Write-Host "Testing prom_query('up')..."
$oneLiner = "import sys; sys.path.insert(0, r'$srcPath'); from tools.prom_query import prom_query; r = prom_query('up'); print('=== prom_query up result ==='); print(r)"
& $pyexe -c $oneLiner
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

# ------------------------------
# 4. 测试 prom_query_range（Unix 秒窗口 + step 整数 -> 15s）
# ------------------------------
Write-Host "Testing prom_query_range('up', last 3600s, step=15)..."
$rangeLiner = "import sys,time; sys.path.insert(0, r'$srcPath'); from tools.prom_query_range import prom_query_range; t=int(time.time()); r=prom_query_range('up',t-3600,t,15); re=r.get('results') or []; print('=== prom_query_range up ==='); print('result_type',r.get('result_type')); print('series',len(re)); print('points_series0',len(re[0]['values']) if re else 0); print(r)"
& $pyexe -c $rangeLiner
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
