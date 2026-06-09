# Sentinel-X Skills（「记」）

Reusable operational knowledge distilled from successful inspect runs.

## Skill vs Evidence

| Layer | Content |
|-------|---------|
| **Skill** (frontmatter) | General pattern: issues, actions, symptom, tags |
| **Evidence** (body) | One-time context: cluster, namespace, pod |

## Layout

```text
skills/
├── README.md
├── TEMPLATE.md
├── examples/          # seed skills (tracked)
├── records/           # runtime upserts (gitignored)
└── .index/skills.db   # SQLite FTS index (gitignored)
```

## Environment

| Variable | Default |
|----------|---------|
| `SENTINEL_SKILLS_DIR` | `{SENTINEL_ROOT}/skills` or repo `skills/` |
| `SENTINEL_SKILLS_DB` | `{SENTINEL_SKILLS_DIR}/.index/skills.db` |
| `SENTINEL_SKILLS_RECORD` | `1` |
| `SENTINEL_SKILLS_SEARCH_LIMIT` | `3` |

## Metadata

| Field | Meaning |
|-------|---------|
| `fingerprint` | `sha256(sorted_issues\|sorted_actions)[:16]` |
| `hit_count` | Total upsert/reference count |
| `source_count` | Distinct Evidence sources (W5: placeholder; W5+ pod dedup) |
| `verified` | `true` only when sandbox verification passes (Ready held ≥ `SENTINEL_SANDBOX_READY_SEC`, default 30s); else `false` |

## Retrieval

W5 uses **SQLite FTS5** with issue synonym expansion (`CrashLoop` → `CrashLoopBackOff`, etc.).

Future: swap backend via `SkillStore` Protocol (`ChromaSkillStore`, etc.) without changing LangGraph nodes.
