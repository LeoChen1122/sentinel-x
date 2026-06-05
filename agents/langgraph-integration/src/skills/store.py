"""SQLite FTS5 skill store with fingerprint deduplication."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from skills.config import SkillsConfig, skills_config
from skills.fingerprint import skill_fingerprint
from skills.models import SkillMatch, SkillRecord, SkillUpsertResult
from skills.parse import compose_skill_markdown, split_frontmatter, summary_from_body

_DEFAULT_STORE: SqliteFtsSkillStore | None = None


class SkillStore(Protocol):
    def upsert_skill(self, markdown: str, *, path: Path | None = None) -> SkillUpsertResult: ...
    def index_all(self) -> int: ...
    def search(self, query: str, *, limit: int = 3) -> list[SkillMatch]: ...
    def get_by_fingerprint(self, fp: str) -> SkillRecord | None: ...


def get_default_store(cfg: SkillsConfig | None = None) -> SqliteFtsSkillStore:
    global _DEFAULT_STORE
    if cfg is None:
        if _DEFAULT_STORE is None:
            _DEFAULT_STORE = SqliteFtsSkillStore(skills_config())
        return _DEFAULT_STORE
    return SqliteFtsSkillStore(cfg)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SqliteFtsSkillStore:
    def __init__(self, cfg: SkillsConfig) -> None:
        self._cfg = cfg
        self._cfg.skills_dir.mkdir(parents=True, exist_ok=True)
        self._cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._cfg.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS skills_meta (
                fingerprint TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 1,
                source_count INTEGER NOT NULL DEFAULT 1,
                verified INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
                name,
                symptom,
                tags,
                issues,
                actions,
                body,
                fingerprint UNINDEXED
            );
            """
        )
        self._conn.commit()

    def _list_markdown_files(self) -> list[Path]:
        roots = [
            self._cfg.skills_dir / "examples",
            self._cfg.skills_dir / "records",
        ]
        out: list[Path] = []
        for root in roots:
            if root.is_dir():
                out.extend(sorted(root.glob("*.md")))
        return out

    def _tags_to_str(self, tags: object) -> str:
        if isinstance(tags, list):
            return " ".join(str(t) for t in tags)
        return str(tags or "")

    def _issues_to_str(self, issues: object) -> str:
        if isinstance(issues, list):
            return " ".join(str(i) for i in issues)
        return str(issues or "")

    def _actions_to_str(self, actions: object) -> str:
        if isinstance(actions, list):
            return " ".join(str(a) for a in actions)
        return str(actions or "")

    def _index_parsed(self, path: Path, fm: dict, body: str) -> None:
        fp = str(fm.get("fingerprint", ""))
        if not fp:
            issues = fm.get("issues") if isinstance(fm.get("issues"), list) else []
            actions = (
                fm.get("recommended_actions")
                if isinstance(fm.get("recommended_actions"), list)
                else []
            )
            fp = skill_fingerprint([str(i) for i in issues], [str(a) for a in actions])
            fm["fingerprint"] = fp

        hit = int(fm.get("hit_count", 1) or 1)
        src = int(fm.get("source_count", 1) or 1)
        verified = 1 if fm.get("verified") is True else 0
        updated = str(fm.get("updated_at") or _utc_now())

        self._conn.execute(
            """
            INSERT INTO skills_meta (fingerprint, path, hit_count, source_count, verified, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                path=excluded.path,
                hit_count=excluded.hit_count,
                source_count=excluded.source_count,
                verified=excluded.verified,
                updated_at=excluded.updated_at
            """,
            (fp, str(path.resolve()), hit, src, verified, updated),
        )
        self._conn.execute("DELETE FROM skills_fts WHERE fingerprint = ?", (fp,))
        self._conn.execute(
            """
            INSERT INTO skills_fts (name, symptom, tags, issues, actions, body, fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(fm.get("name", "")),
                str(fm.get("symptom", "")),
                self._tags_to_str(fm.get("tags")),
                self._issues_to_str(fm.get("issues")),
                self._actions_to_str(fm.get("recommended_actions")),
                body,
                fp,
            ),
        )

    def index_file(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)
        if not fm:
            return
        self._index_parsed(path, fm, body)
        self._conn.commit()

    def index_all(self) -> int:
        count = 0
        for path in self._list_markdown_files():
            self.index_file(path)
            count += 1
        self._conn.commit()
        return count

    def get_by_fingerprint(self, fp: str) -> SkillRecord | None:
        row = self._conn.execute(
            "SELECT * FROM skills_meta WHERE fingerprint = ?", (fp,)
        ).fetchone()
        if row is None:
            return None
        path = Path(row["path"])
        if not path.is_file():
            return None
        fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
        return self._record_from_parts(path, fm, body, row)

    def _record_from_parts(self, path: Path, fm: dict, body: str, row: sqlite3.Row | None = None) -> SkillRecord:
        issues = fm.get("issues") if isinstance(fm.get("issues"), list) else []
        actions = (
            fm.get("recommended_actions")
            if isinstance(fm.get("recommended_actions"), list)
            else []
        )
        hit = int(row["hit_count"]) if row is not None else int(fm.get("hit_count", 1) or 1)
        src = int(row["source_count"]) if row is not None else int(fm.get("source_count", 1) or 1)
        verified = bool(row["verified"]) if row is not None else fm.get("verified") is True
        fp = str(fm.get("fingerprint", ""))
        return SkillRecord(
            name=str(fm.get("name", "")),
            symptom=str(fm.get("symptom", "")),
            summary=summary_from_body(body),
            fingerprint=fp,
            path=str(path),
            hit_count=hit,
            source_count=src,
            verified=verified,
            issues=[str(i) for i in issues],
            recommended_actions=[str(a) for a in actions],
            body=body,
            markdown=compose_skill_markdown(fm, body),
        )

    def upsert_skill(self, markdown: str, *, path: Path | None = None) -> SkillUpsertResult:
        fm, body = split_frontmatter(markdown)
        issues = fm.get("issues") if isinstance(fm.get("issues"), list) else []
        actions = (
            fm.get("recommended_actions")
            if isinstance(fm.get("recommended_actions"), list)
            else []
        )
        fp = skill_fingerprint([str(i) for i in issues], [str(a) for a in actions])
        fm["fingerprint"] = fp
        now = _utc_now()
        fm.setdefault("created_at", now)
        fm["updated_at"] = now

        existing = self.get_by_fingerprint(fp)
        records_dir = self._cfg.skills_dir / "records"
        records_dir.mkdir(parents=True, exist_ok=True)

        if existing is not None:
            hit = int(existing.get("hit_count", 1)) + 1
            src = int(existing.get("source_count", 1)) + 1
            fm["hit_count"] = hit
            fm["source_count"] = src
            fm.setdefault("name", existing.get("name", fm.get("name", "skill")))
            target = Path(existing["path"])
            if not target.is_file() and path is not None:
                target = path
        else:
            hit = int(fm.get("hit_count", 1) or 1)
            src = int(fm.get("source_count", 1) or 1)
            fm["hit_count"] = hit
            fm["source_count"] = src
            name = str(fm.get("name", "skill"))
            target = path or (records_dir / f"{name}.md")

        text = compose_skill_markdown(fm, body)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        self._index_parsed(target, fm, body)
        self._conn.commit()
        return SkillUpsertResult(
            fingerprint=fp,
            path=str(target),
            created=existing is None,
            hit_count=hit,
            source_count=src,
        )

    def search(self, query: str, *, limit: int = 3) -> list[SkillMatch]:
        if not query.strip():
            return []
        if self._conn.execute("SELECT COUNT(*) FROM skills_meta").fetchone()[0] == 0:
            self.index_all()

        rows = self._conn.execute(
            """
            SELECT
                m.fingerprint,
                m.path,
                m.hit_count,
                m.source_count,
                m.verified,
                fts.name,
                fts.symptom,
                fts.body,
                bm25(skills_fts) AS score
            FROM skills_fts fts
            JOIN skills_meta m ON m.fingerprint = fts.fingerprint
            WHERE skills_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (query, limit * 3),
        ).fetchall()

        seen: set[str] = set()
        out: list[SkillMatch] = []
        for row in rows:
            fp = row["fingerprint"]
            if fp in seen:
                continue
            seen.add(fp)
            body = row["body"] or ""
            out.append(
                SkillMatch(
                    name=row["name"] or "",
                    symptom=row["symptom"] or "",
                    summary=summary_from_body(body),
                    fingerprint=fp,
                    path=row["path"] or "",
                    score=float(row["score"] or 0.0),
                    hit_count=int(row["hit_count"] or 1),
                    source_count=int(row["source_count"] or 1),
                    verified=bool(row["verified"]),
                )
            )
            if len(out) >= limit:
                break
        return out
