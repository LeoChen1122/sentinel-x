# ADR-003: Why Docker Sandbox

## Status

Accepted (2026-06-17)

## Context

The execute node can propose remediation (`restart_pod`, etc.). Running kubectl on the **host** that also holds production kubeconfig risks:

- Accidental writes to `kube-system` or tenant namespaces
- Shell injection if narrative/LLM output reaches a shell
- No audit trail isolated from the agent process

Alternatives considered:

- **Host kubectl with RBAC ServiceAccount** — simpler ops, still shares network/FS with agent
- **gVisor / Firecracker microVM** — stronger isolation; deferred (ROADMAP W8+)
- **Always dry_run** — safe but no path to validated auto-remediation

## Decision

Use a **Docker-based sandbox executor** for non-dry-run runs:

- Image: `sentinel-x-sandbox:latest` ([`sandbox/`](../../sandbox/))
- Manager: [`agents/langgraph-integration/src/sandbox/`](../../agents/langgraph-integration/src/sandbox/)
- Graph node: `sandbox_run` in [`graph.py`](../../agents/langgraph-server/src/graph.py)
- **Namespace allowlist**: only `sentinel-sandbox` (fixture pods like `crash-demo`)
- Production cluster writes require future `SENTINEL_EXECUTE_LIVE=1` (explicitly `NotImplementedError` today)

Default everywhere else: `dry_run=true` (patrol, API, webhooks).

## Consequences

**Positive**

- Demonstrates real kubectl in CI/server without touching prod namespaces
- Audit logs from container runs; verify script exercises sandbox in `--full`
- Clear upgrade path: tighten policy → expand allowlist → gated live execute

**Negative**

- Requires Docker on server; image build step in install
- Not true multi-tenant isolation (shared Docker daemon)
- gVisor-class isolation still on backlog

## References

- [Sandbox architecture](../architecture/sandbox.md)
- [DEPLOY-ONE-SHOT.md](../deploy/DEPLOY-ONE-SHOT.md) — `--with-sandbox`
