# Prepare offline kube-prometheus-stack bundle on a Windows PC with internet.
# Upload the output folder to sentinel-x server (scp / WinSCP).
#
# Usage (PowerShell):
#   cd C:\sentinel-x\deploy\prometheus
#   .\prepare-kube-prometheus-offline.ps1
#   .\prepare-kube-prometheus-offline.ps1 -FromZip C:\Downloads\helm-charts-main.zip
#
# Requires: helm 3.x in PATH (https://helm.sh/docs/intro/install/)

param(
    [string]$OutDir = "$PSScriptRoot\..\..\dist\kube-prometheus-offline",
    [string]$ChartVersion = "",   # empty = latest from repo
    [string]$FromZip = ""
)

$ErrorActionPreference = "Stop"

function Require-Helm {
    if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
        throw "helm not found in PATH. Install Helm 3: https://helm.sh/docs/intro/install/"
    }
    helm version --short
}

function Prepare-FromHelmPull {
    param([string]$Target)
    Remove-Item -Recurse -Force $Target -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $Target | Out-Null

    Write-Host "Adding prometheus-community repo..."
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>$null
    helm repo update prometheus-community

    Push-Location $Target
    try {
        if ($ChartVersion) {
            helm pull prometheus-community/kube-prometheus-stack --version $ChartVersion --untar
        } else {
            helm pull prometheus-community/kube-prometheus-stack --untar
        }
        if (-not (Test-Path "kube-prometheus-stack\Chart.yaml")) {
            throw "helm pull did not produce kube-prometheus-stack/"
        }
        Write-Host "OK: chart at $Target\kube-prometheus-stack"
    } finally {
        Pop-Location
    }
}

function Prepare-FromMonorepoZip {
    param([string]$ZipPath, [string]$Target)

    if (-not (Test-Path $ZipPath)) {
        throw "Zip not found: $ZipPath"
    }

    $staging = Join-Path $env:TEMP "helm-charts-pack-$(Get-Random)"
    New-Item -ItemType Directory -Force -Path $staging | Out-Null
    Expand-Archive -Path $ZipPath -DestinationPath $staging -Force

    $root = Get-ChildItem $staging -Directory | Where-Object { Test-Path (Join-Path $_.FullName "charts\kube-prometheus-stack") } | Select-Object -First 1
    if (-not $root) {
        $root = Get-ChildItem $staging -Directory | Select-Object -First 1
    }
    $chartsRoot = Join-Path $root.FullName "charts"
    if (-not (Test-Path (Join-Path $chartsRoot "kube-prometheus-stack\Chart.yaml"))) {
        throw "Could not find charts/kube-prometheus-stack in zip. Expected prometheus-community/helm-charts layout."
    }

    $localRepo = Join-Path $staging "local-repo"
    New-Item -ItemType Directory -Force -Path $localRepo | Out-Null

    Write-Host "Packaging charts from monorepo (this may take a minute)..."
    Get-ChildItem $chartsRoot -Directory | ForEach-Object {
        helm package $_.FullName -d $localRepo | Out-Null
    }
    helm repo index $localRepo

    Remove-Item -Recurse -Force $Target -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    Copy-Item -Recurse $localRepo (Join-Path $Target "helm-local-repo")
    Copy-Item -Recurse (Join-Path $chartsRoot "kube-prometheus-stack") (Join-Path $Target "kube-prometheus-stack-src")

    @"
# Generated from helm-charts-main.zip — use install script with HELM_OFFLINE_REPO
HELM_OFFLINE_REPO=$Target/helm-local-repo
"@ | Set-Content -Encoding utf8 (Join-Path $Target "OFFLINE.txt")

    Remove-Item -Recurse -Force $staging
    Write-Host "OK: local repo at $Target\helm-local-repo"
}

Require-Helm
$OutDir = [System.IO.Path]::GetFullPath($OutDir)
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if ($FromZip) {
    Prepare-FromMonorepoZip -ZipPath $FromZip -Target $OutDir
} else {
    Prepare-FromHelmPull -Target $OutDir
}

# Copy server install assets into bundle (deploy/prometheus/ is canonical source)
$deployProm = $PSScriptRoot
Copy-Item (Join-Path $deployProm "kube-prometheus-values-minimal.yaml") $OutDir -Force
$installSh = Join-Path $deployProm "install-kube-prometheus-offline.sh"
Copy-Item $installSh $OutDir -Force
# Mark dist copy as generated
$distInstall = Join-Path $OutDir "install-kube-prometheus-offline.sh"
$content = Get-Content $distInstall -Raw
if ($content -notmatch "DO NOT EDIT") {
    $header = "# DO NOT EDIT — copy from deploy/prometheus/install-kube-prometheus-offline.sh via prepare-kube-prometheus-offline.ps1`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($distInstall, $header + $content, $utf8NoBom)
}

Write-Host ""
Write-Host "=== Upload to server ==="
Write-Host "  scp -r `"$OutDir`" root@sentinel-x:/opt/sentinel-x/dist/"
Write-Host ""
Write-Host "=== On server ==="
Write-Host "  cd /opt/sentinel-x/dist/kube-prometheus-offline"
Write-Host "  sudo bash install-kube-prometheus-offline.sh"
