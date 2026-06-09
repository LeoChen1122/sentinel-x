# Sentinel-X Sandbox（「试」）

Isolated pre-run for risky kubectl actions. **Production namespaces are never written.**

## Isolation model (W6)

| Layer | Behavior |
|-------|----------|
| **Policy** | Only `SENTINEL_SANDBOX_NAMESPACE` (default `sentinel-sandbox`) |
| **Docker** | Read-only rootfs, `kubectl` entrypoint, kubeconfig mounted ro |
| **Network** | `--network host` so API server URL in kubeconfig remains reachable |
| **Verification (W6.1)** | `restart_pod`: Deployment pods must stay **Ready** for `SENTINEL_SANDBOX_READY_SEC` (default 30s) |
| **scale_up** | **Deployment only**; `replicas <= SENTINEL_SANDBOX_MAX_REPLICAS` |

k3s uses **containerd**; Docker is **only** for sandbox command execution (same as MCP compose).

## Layout

```text
sandbox/
├── Dockerfile
├── fixtures/crash-loop-deployment.yaml
├── audit/              # audit-YYYY-MM.jsonl (monthly rotation)
└── README.md
```

## Setup

```bash
docker build -t sentinel-x-sandbox:latest sandbox/
kubectl apply -f sandbox/fixtures/crash-loop-deployment.yaml
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTINEL_SANDBOX_ENABLED` | `1` | `0` disables `sandbox_run` |
| `SENTINEL_SANDBOX_NAMESPACE` | `sentinel-sandbox` | Only namespace allowed for writes |
| `SENTINEL_SANDBOX_AUDIT_DIR` | `{SENTINEL_ROOT}/sandbox/audit` | JSONL audit root |
| `SENTINEL_SANDBOX_IMAGE` | `sentinel-x-sandbox:latest` | Executor image |
| `SENTINEL_SANDBOX_TIMEOUT_SEC` | `60` | Per-command timeout |
| `SENTINEL_SANDBOX_MAX_REPLICAS` | `5` | scale_up cap |
| `SENTINEL_SANDBOX_READY_SEC` | `30` | Ready must hold this long for `verified` |
| `SENTINEL_SANDBOX_VERIFY_POLL_SEC` | `5` | Verification poll interval |
| `SENTINEL_SANDBOX_VERIFY_TIMEOUT_SEC` | `120` | Max wait for verification |
| `SENTINEL_SANDBOX_PAYLOAD_TRUNCATE` | `4096` | stdout/stderr in graph payload (audit keeps full text) |

## Execution modes

| `dry_run` | `SENTINEL_EXECUTE_LIVE` | Result |
|-----------|-------------------------|--------|
| `true` | — | Simulated only |
| `false` | off | Sandbox kubectl + audit + verification |
| `false` | `1` | Not implemented (W8+) |

## Audit (monthly files)

```text
sandbox/audit/audit-2026-06.jsonl
sandbox/audit/audit-2026-07.jsonl
```

Each line includes full `stdout`/`stderr`. Graph `sandbox_result.runs[]` carries truncated copies for UI/narrative.

**Retention (manual):** archive or compress files older than 6 months (no auto-cleanup in W6.1).

## Skill verification

`verified: true` only when:

1. kubectl command succeeds, and
2. For `restart_pod`: Deployment pods **Ready** for `READY_SEC` without returning to CrashLoopBackOff

## Acceptance

```bash
POD=$(kubectl get pods -n sentinel-sandbox -l app=crash-demo -o jsonpath='{.items[0].metadata.name}')
python agents/langgraph-integration/scripts/demo/sandbox_demo.py \
  --namespace sentinel-sandbox --pod-name "$POD"
```

Inspect outside `sentinel-sandbox` → actions **blocked** (audit only, no kubectl).
