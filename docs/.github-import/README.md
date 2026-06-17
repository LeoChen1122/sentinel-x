# GitHub Import Checklist

Use these files to set up GitHub **Projects** and **Releases** manually (no gh CLI required).

## 1. Project board

1. GitHub → **Projects** → **New project** → Board
2. Columns: **Backlog** | **Doing** | **Review** | **Done**
3. Open [`ISSUES.md`](ISSUES.md) → create issues → drag into columns

Suggested initial placement:

| Column | Items |
|--------|-------|
| Done | W1–W7 MVP, one-shot deploy, patrol, sandbox dry-run |
| Doing | Alertmanager webhook live, SQLite checkpoint |
| Backlog | Everything else in ISSUES.md |

## 2. Releases

1. GitHub → **Releases** → **Draft a new release**
2. For each tag `v0.1.0` … `v0.4.0`, paste body from [`RELEASES.md`](RELEASES.md)
3. Optional local tags (do not force-push):

```bash
git tag v0.1.0 <commit-for-v0.1>
git tag v0.2.0 <commit-for-v0.2>
git tag v0.3.0 <commit-for-v0.3>
git tag v0.4.0 HEAD
git push origin v0.4.0
```

## 3. Changelog

Keep [`CHANGELOG.md`](../../CHANGELOG.md) updated on each release; RELEASES.md mirrors GitHub release notes.
