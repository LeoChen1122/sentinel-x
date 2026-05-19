"""Incremental sync state: skip unchanged entities by fingerprint."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from functools import lru_cache
from pathlib import Path

from models.entities import GraphBatch, GraphEntity

logger = logging.getLogger(__name__)


def _properties_json(properties: dict) -> str:
    return json.dumps(properties, sort_keys=True, default=str)


@lru_cache(maxsize=8192)
def _fingerprint_from_parts(type_value: str, entity_id: str, properties_json: str) -> str:
    """Hash type + id + properties JSON (cached by parts; avoids duplicate SHA256 work)."""
    payload = f"{type_value}\0{entity_id}\0{properties_json}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def entity_fingerprint(entity: GraphEntity) -> str:
    """Stable hash of entity type, id, and properties.

    ``GraphEntity`` is a slotted dataclass (no weakref); fingerprints are cached
    via LRU on ``(type, id, properties_json)`` so large batches avoid repeat SHA256.
    """
    props_json = _properties_json(entity.properties)
    return _fingerprint_from_parts(entity.type.value, entity.id, props_json)


def clear_entity_fingerprint_cache() -> None:
    """Clear fingerprint LRU cache (mainly for tests)."""
    _fingerprint_from_parts.cache_clear()


def sync_state_partition_key(cluster_id: str, tenant_id: str | None = None) -> str:
    """Filesystem-safe key for ``SyncState`` partition (tenant/cluster)."""
    tenant = (tenant_id or "default").strip() or "default"
    cid = cluster_id.strip()
    if not cid:
        raise ValueError("cluster_id required for sync state partition")
    safe_tenant = tenant.replace("/", "_").replace("\\", "_")
    safe_cluster = cid.replace("/", "_").replace("\\", "_")
    return f"{safe_tenant}/{safe_cluster}"


def partition_state_path(
    base: Path | None,
    cluster_id: str,
    tenant_id: str | None = None,
) -> Path | None:
    """Resolve per-partition JSON path under ``LANGGRAPH_SYNC_STATE_PATH``."""
    if base is None:
        return None
    key = sync_state_partition_key(cluster_id, tenant_id)
    if base.suffix.lower() == ".json":
        return base.parent / "partitions" / f"{key}.json"
    return base / "partitions" / f"{key}.json"


class SyncState:
    """Tracks last-pushed entity fingerprints for incremental sync."""

    def __init__(self, *, path: str | Path | None = None) -> None:
        self._fingerprints: dict[str, str] = {}
        self._path = Path(path) if path else None
        if self._path:
            self._load()

    def _load(self) -> None:
        if not self._path or not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._fingerprints = {str(k): str(v) for k, v in raw.items()}
        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.warning("Could not load sync state from %s: %s", self._path, e)

    def save(self) -> None:
        """Persist fingerprints via atomic replace (tmp file then ``os.replace``).

        Reduces risk of torn writes on crash. Multiple processes writing the same
        path concurrently still need an external file lock; not handled here.
        """
        if not self._path:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._path.with_name(self._path.name + ".tmp")
            tmp_path.write_text(
                json.dumps(self._fingerprints, sort_keys=True),
                encoding="utf-8",
            )
            os.replace(tmp_path, self._path)
        except OSError as e:
            logger.warning("Could not save sync state to %s: %s", self._path, e)

    @classmethod
    def from_env(cls) -> SyncState:
        path = os.getenv("LANGGRAPH_SYNC_STATE_PATH", "").strip()
        return cls(path=path or None)

    @classmethod
    def for_scope(
        cls,
        cluster_id: str,
        tenant_id: str | None = None,
        *,
        base_path: str | Path | None = None,
    ) -> SyncState:
        """Partitioned incremental state for one cluster (and optional tenant)."""
        base: Path | None
        if base_path is not None:
            base = Path(base_path) if str(base_path).strip() else None
        else:
            env = os.getenv("LANGGRAPH_SYNC_STATE_PATH", "").strip()
            base = Path(env) if env else None
        path = partition_state_path(base, cluster_id, tenant_id)
        return cls(path=path)

    def filter_batch(self, batch: GraphBatch) -> tuple[GraphBatch, int]:
        """Return only new or changed entities; drop edges whose endpoints were removed.

        Empty input: returns ``(GraphBatch(), 0)`` — no entities, no edges, nothing
        skipped (there is nothing to compare against incoming rows).
        """
        if not batch.entities and not batch.edges:
            return GraphBatch(), 0

        kept: list[GraphEntity] = []
        skipped = 0
        for ent in batch.entities:
            fp = entity_fingerprint(ent)
            if self._fingerprints.get(ent.id) == fp:
                skipped += 1
                continue
            kept.append(ent)

        if not kept:
            return GraphBatch(entities=[], edges=[]), skipped

        kept_ids = {e.id for e in kept}
        edges = [
            e
            for e in batch.edges
            if e.source_id in kept_ids and e.target_id in kept_ids
        ]
        return GraphBatch(entities=kept, edges=edges), skipped

    def update_from_batch(self, batch: GraphBatch) -> None:
        """Record fingerprints for entities in ``batch`` and persist if configured.

        Empty ``batch.entities``: no-op (does not clear stored state).
        """
        if not batch.entities:
            return
        for ent in batch.entities:
            self._fingerprints[ent.id] = entity_fingerprint(ent)
        self.save()

    def fingerprint_for(self, entity_id: str) -> str | None:
        return self._fingerprints.get(entity_id)


class SyncStateRegistry:
    """In-process cache of :class:`SyncState` per tenant+cluster partition."""

    def __init__(self, *, base_path: str | Path | None = None) -> None:
        if base_path is not None and str(base_path).strip():
            self._base_path: Path | None = Path(base_path)
        else:
            env = os.getenv("LANGGRAPH_SYNC_STATE_PATH", "").strip()
            self._base_path = Path(env) if env else None
        self._states: dict[str, SyncState] = {}

    @classmethod
    def from_env(cls) -> SyncStateRegistry:
        return cls()

    def get(self, cluster_id: str, tenant_id: str | None = None) -> SyncState:
        key = sync_state_partition_key(cluster_id, tenant_id)
        if key not in self._states:
            path = partition_state_path(self._base_path, cluster_id, tenant_id)
            self._states[key] = SyncState(path=path)
        return self._states[key]

    def clear_cache(self) -> None:
        """Drop in-memory instances (tests)."""
        self._states.clear()
