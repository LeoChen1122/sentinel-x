# GitHub Import Checklist / GitHub 导入指南

Set up GitHub **Projects** and **Releases** in the browser — no `gh` CLI required.  
**无需 gh CLI**，在 GitHub 网页端手动搭建 Project 看板与 Release 发布（简历 / 面试向）。

---

## Files in this directory | 本目录文件

| File | English | 中文 |
|------|---------|------|
| [README.md](README.md) | This guide (bilingual) | 本指南（中英双语） |
| [ISSUES.md](ISSUES.md) | Issue titles + bodies for Project board | 看板 Issue 模板 |
| [RELEASES.md](RELEASES.md) | v0.1.0–v0.4.0 release notes (paste to GitHub) | 发布说明（粘贴到 Release 表单） |
| [CHANGELOG.md](../../CHANGELOG.md) | Version history | 版本变更总账 |

**Related docs | 相关文档**

- Done items evidence → [`docs/weekly/`](../weekly/README.md) (W22–W26)
- Engineering roadmap → [`docs/ROADMAP.md`](../ROADMAP.md)
- This folder is for **external GitHub presentation** only.  
  本目录只管 **GitHub 对外展示**；工程细节仍以 ROADMAP / weekly 为准。

---

## Workflow | 整体流程

```text
① Push repo (incl. docs/.github-import/)     推送代码
② Create Project board (4 columns)           创建看板四列
③ Create issues from ISSUES.md → drag        按 ISSUES 建 Issue 并拖列
④ Publish v0.1.0 → v0.4.0 from RELEASES.md   按 RELEASES 发版
⑤ Optional: git tag + push                   可选：本地打 tag
⑥ Ongoing: Issue → Doing → Done + CHANGELOG  日常：看板 + 变更日志
```

**Time | 耗时:** ~30–60 min first time / 首次约 30–60 分钟

---

## 1. Project board | 看板搭建

### Steps | 步骤

1. GitHub repo → **Projects** → **New project** → **Board**  
   打开仓库 → **Projects** → **New project** → 选 **Board**
2. Name e.g. `Sentinel-X Roadmap`  
   建议命名：`Sentinel-X Roadmap`
3. Columns | 列：**Backlog** | **Doing** | **Review** | **Done**
4. Open [`ISSUES.md`](ISSUES.md) → **New issue** per row → drag to column  
   打开 ISSUES.md → 每行建 Issue → 拖入对应列

### Column guide | 列说明

| Column | English | 中文 |
|--------|---------|------|
| **Backlog** | Planned, not started | 计划做、尚未开工 |
| **Doing** | In progress (max 2–3) | 进行中（建议 ≤2–3 项） |
| **Review** | PR awaiting review (optional) | PR 待 review（可选） |
| **Done** | Completed | 已完成 |

### Suggested placement | 建议初始分布

| Column | Items |
|--------|-------|
| **Done** | W1–W7 MVP, one-shot deploy, patrol, sandbox, POST /v1/inspect |
| **Doing** | Alertmanager webhook live, SQLite checkpoint |
| **Backlog** | All other rows in ISSUES.md |

Close **Done** issues after moving them — shows velocity.  
**Done** 项拖入后 **Close issue**，体现迭代速度。

### Labels (optional) | 标签（可选）

`enhancement` · `ops` · `agent` · `sandbox` · `docs`

### Bulk tips | 批量技巧

1. Create **Backlog** first (fills the board) / 先建 Backlog（看板立刻丰满）
2. Then **Done** + close / 再建 Done 并关闭
3. Keep **Doing** at 2–3 items / Doing 控制在 2–3 项
4. **Review**: link PR in issue body / Review 列正文贴 PR 链接

**Target look | 目标效果:** `Done(8+) · Doing(2) · Backlog(12+)`

---

## 2. Releases | 版本发布

### Version map | 版本对照

| Tag | Theme (EN) | 主题（中文） |
|-----|------------|--------------|
| `v0.1.0` | Monitoring MVP | 监控 MVP：K8s MCP、sync |
| `v0.2.0` | Agent Runtime | Agent 运行时：LangGraph 流水线 |
| `v0.3.0` | Prometheus MCP | Prom MCP、指标进图 |
| `v0.4.0` | One-shot + Alert Close | 一键部署 + W7 告警闭环 |

### Steps (repeat per version) | 步骤（每版重复）

1. **Releases** → **Draft a new release**
2. **Tag:** `v0.1.0` … `v0.4.0` → **Create new tag on publish**
3. **Title + Describe:** copy from [`RELEASES.md`](RELEASES.md) (`Added` / `Changed` / `Fixed`)
4. **Set as latest release** — only for `v0.4.0`  
   **设为 latest** — 仅 v0.4.0 需要
5. **Publish release**

Order | 顺序: **v0.1.0 → v0.2.0 → v0.3.0 → v0.4.0**

### Optional local tags | 可选本地 tag

```bash
git tag v0.1.0 <commit-for-v0.1>
git tag v0.2.0 <commit-for-v0.2>
git tag v0.3.0 <commit-for-v0.3>
git tag v0.4.0 HEAD
git push origin v0.1.0 v0.2.0 v0.3.0 v0.4.0
```

Do **not** `git push --force` on existing tags.  
**不要**对已存在的 tag 使用 `git push --force`。

Replace `your-org/sentinel-x` in [CHANGELOG.md](../../CHANGELOG.md) with your repo URL.  
将 CHANGELOG 中的 `your-org/sentinel-x` 改为你的仓库地址。

---

## 3. Changelog sync | 变更日志同步

- Keep [CHANGELOG.md](../../CHANGELOG.md) aligned with GitHub Release bodies.  
  Release 正文与 CHANGELOG 保持一致。
- New work → `[Unreleased]`; on release → `[x.y.z] - date`.  
  新功能先写 `[Unreleased]`，发版时改为 `[x.y.z] - 日期`。

---

## 4. Ongoing maintenance | 日常维护

| Cadence | English | 中文 |
|---------|---------|------|
| Weekly | `docs/weekly/YYYY-Www.md` — detailed engineering | 详细工程周报 |
| Dev log | `docs/dev-log/YYYY-MM-DD.md` — 5-min portfolio snapshot | 5 分钟对外摘要 |
| Board | Move issues Done + close; pull from Backlog → Doing | 看板拖列 + 关单 |

### Commit style | Commit 规范

**Good | 推荐** (3–10 quality commits / week):

```text
feat(sandbox): add isolated docker executor
docs(adr): explain MCP architecture decision
```

**Avoid | 避免:** `fix typo` × 20/day — obvious commit-graph padding.  
避免一天大量 `fix typo` 刷活跃度。

---

## 5. FAQ | 常见问题

| Q | EN | 中文 |
|---|-----|------|
| Duplicate ROADMAP? | ROADMAP = dev detail; Issues = external board | ROADMAP 给开发者；Issues 给外部读者 |
| No gh CLI? | By design; optional later with `gh issue create` | 刻意网页操作；以后可用 gh 自动化 |
| Releases with zero downloads? | Still worth it — maturity signal | 仍值得发 — 体现版本边界与成熟度 |
| Demo assets? | [`docs/assets/demo/`](../assets/demo/) | 截图/GIF 放此目录 |

---

## 6. Checklist | 验收清单

- [ ] Project board: 4 columns, Done ≥ 8, Doing 2–3, Backlog ≥ 10  
      看板四列齐全，Done ≥ 8，Doing 2–3，Backlog ≥ 10
- [ ] Releases: v0.1.0–v0.4.0 published  
      Releases 页面共 4 个版本
- [ ] CHANGELOG repo URLs updated  
      CHANGELOG 链接已改为真实仓库
- [ ] At least one dev-log entry  
      至少 1 篇 dev-log（如 [2026-06-17](../dev-log/2026-06-17.md)）

---

## Links | 相关链接

| | |
|--|--|
| [README](../../README.md) | Repo home / 仓库首页 |
| [Architecture](../architecture/README.md) | Diagrams / 架构图 |
| [ADR](../adr/README.md) | Decision records / 架构决策 |
| [Dev log](../dev-log/README.md) | Portfolio log / 开发日志 |
| [DEPLOY-ONE-SHOT](../deploy/DEPLOY-ONE-SHOT.md) | One-shot install / 一键部署 |
