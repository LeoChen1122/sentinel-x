#!/usr/bin/env bash
# Capture demo text outputs on production server for README screenshots.
set -euo pipefail
OUT=/tmp/sentinel-demo-capture
mkdir -p "$OUT"
POD=$(kubectl get pods -n sentinel-sandbox -l app=crash-demo -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo crash-demo)
TOKEN=$(grep '^SENTINEL_API_TOKEN=' /etc/sentinel/sentinel-api.env 2>/dev/null | cut -d= -f2- || true)

echo "POD=$POD" >"$OUT/meta.txt"

# 1) Inspect via API
if [[ -n "$TOKEN" ]]; then
  curl -sf -m 120 -X POST http://127.0.0.1:8080/v1/inspect \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d "{\"pod_name\":\"${POD}\",\"namespace\":\"sentinel-sandbox\",\"dry_run\":true}" \
    | python3 -m json.tool >"$OUT/inspect.json" 2>/dev/null || echo '{"ok":false}' >"$OUT/inspect.json"
else
  curl -sf -m 120 -X POST http://127.0.0.1:8080/v1/inspect \
    -H "Content-Type: application/json" \
    -d "{\"pod_name\":\"${POD}\",\"namespace\":\"sentinel-sandbox\",\"dry_run\":true}" \
    | python3 -m json.tool >"$OUT/inspect.json" 2>/dev/null || echo '{"ok":false}' >"$OUT/inspect.json"
fi

# 2) Sandbox demo
export SENTINEL_ROOT=/opt/sentinel-x
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
/opt/sentinel-x/.venv/bin/python \
  /opt/sentinel-x/agents/langgraph-integration/scripts/demo/sandbox_demo.py \
  --pod-name "$POD" --namespace sentinel-sandbox --cluster-id k3s-prod --dry-run \
  >"$OUT/sandbox.txt" 2>&1 || true

# 3) Streamlit / UI summary via list_pods + inspect snippet
source /etc/sentinel/sync-k8s.env 2>/dev/null || true
/opt/sentinel-x/.venv/bin/python - <<'PY' >"$OUT/ui.txt" 2>&1
import os, json, sys
sys.path.insert(0, "/opt/sentinel-x/agents/langgraph-integration/src")
from clients.langgraph_client import query_sentinel, get_langgraph_client
tid = os.environ.get("LANGGRAPH_THREAD_ID", "")
cid = os.environ.get("CLUSTER_ID", "k3s-prod")
ns = os.environ.get("NAMESPACE", "kube-system")
c = get_langgraph_client()
pods = query_sentinel("list_pods", thread_id=tid, client=c, cluster_id=cid, namespace=ns)
cpu = query_sentinel("top_pods_by_cpu", thread_id=tid, client=c, cluster_id=cid, namespace=ns, limit=5)
print("=== Sentinel-X Streamlit UI (data snapshot) ===")
print(f"thread_id: {tid[:8]}...")
print(f"cluster: {cid}  namespace: {ns}")
print("\n--- list_pods (sample) ---")
for p in (pods.get("pods") or [])[:6]:
    print(f"  {p.get('name','?'):40} phase={p.get('status', p.get('phase','?'))}")
print(f"  ... count={pods.get('count', len(pods.get('pods') or []))}")
print("\n--- top_pods_by_cpu ---")
for p in (cpu.get("pods") or cpu.get("results") or [])[:5]:
    if isinstance(p, dict):
        print(f"  {p.get('name','?'):40} cpu={p.get('cpu_cores', p.get('cpu','?'))}")
PY

tar -czf /tmp/sentinel-demo-capture.tgz -C /tmp sentinel-demo-capture
echo "WROTE /tmp/sentinel-demo-capture.tgz"
