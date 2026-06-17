# ADR-004: Why One-Shot Deploy

## Status

Accepted (2026-06-17)

## Context

Sentinel-X targets a **single Linux server** (k3s + LangGraph + MCP + optional UI/API/Prometheus). Operators need:

- Repeatable install after OS rebuild or new cloud VM
- Offline-friendly bundles (air-gapped or slow networks)
- Idempotent config without hand-editing a dozen env files

Alternatives considered:

- **Helm-only** — good for K8s apps, weak for host systemd + docker compose + cron on bare metal
- **Ansible/Terraform full stack** — powerful, heavy for solo MVP velocity
- **Manual runbooks only** — documented in W22–W24 weekly; error-prone at scale

## Decision

Use **bash one-shot installer + generated env + systemd**:

| Piece | Path |
|-------|------|
| Main installer | `deploy/install/install-sentinel-x.sh` |
| Config render | `deploy/config/sentinel-config-apply.sh` |
| Master env | `/etc/sentinel/sentinel-x.env` ← `deploy/config/sentinel-x.env.example` |
| Verify | `deploy/verify/verify-sentinel-x.sh --full` |
| Offline Prom | `dist/kube-prometheus-offline/` |
| Reset | `deploy/install/reset-sentinel-x.sh` |

Flags compose optional layers: `--with-ui`, `--with-api`, `--with-sandbox`, `--with-prometheus`, `--with-fixtures`.

Helm is used **inside** the offline Prometheus bundle, not as the top-level Sentinel-X installer.

## Consequences

**Positive**

- W25 live evidence: reset → install → `verify --full` on production server
- Single source of truth for thread_id, MCP containers, patrol env
- Fits resume narrative: "one-command SRE agent platform on k3s"

**Negative**

- Bash/systemd is Linux-specific; no first-class Windows server path
- CRLF on Windows-edited scripts breaks on server (mitigate via `.gitattributes` + `sed`)
- Version pinning split across pip, docker images, and offline tarballs

## References

- [DEPLOY-ONE-SHOT.md](../deploy/DEPLOY-ONE-SHOT.md)
- [DEPLOY-REFERENCE.md](../deploy/DEPLOY-REFERENCE.md)
- [Weekly W25](../weekly/2026-W25.md)
