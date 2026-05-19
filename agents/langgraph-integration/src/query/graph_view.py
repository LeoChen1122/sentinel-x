"""In-memory view over a sync ``payload`` (entities + edges)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from models.entities import EntityType, RelationType
from models.ids import pod_id


@dataclass
class GraphView:
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> GraphView:
        view = cls()
        for ent in payload.get("entities") or []:
            if isinstance(ent, dict) and ent.get("id"):
                view.entities[str(ent["id"])] = ent
        for edge in payload.get("edges") or []:
            if isinstance(edge, dict):
                view.edges.append(edge)
        return view

    def to_payload(self) -> dict[str, Any]:
        return {
            "entities": list(self.entities.values()),
            "edges": list(self.edges),
        }

    def merge_payload(self, payload: dict[str, Any]) -> None:
        """Merge entities by id and dedupe edges."""
        for ent in payload.get("entities") or []:
            if isinstance(ent, dict) and ent.get("id"):
                self.entities[str(ent["id"])] = ent
        seen: set[tuple[str, str, str]] = set()
        merged: list[dict[str, Any]] = []
        for edge in self.edges:
            key = (
                str(edge.get("source_id", "")),
                str(edge.get("target_id", "")),
                str(edge.get("relation", "")),
            )
            seen.add(key)
            merged.append(edge)
        for edge in payload.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            key = (
                str(edge.get("source_id", "")),
                str(edge.get("target_id", "")),
                str(edge.get("relation", "")),
            )
            if key not in seen:
                seen.add(key)
                merged.append(edge)
        self.edges = merged

    def entities_by_type(self, entity_type: str) -> list[dict[str, Any]]:
        return [
            e
            for e in self.entities.values()
            if str(e.get("type", "")).lower() == entity_type.lower()
        ]

    def pod_entity_id(self, cluster_id: str, namespace: str, name: str) -> str:
        return pod_id(cluster_id, namespace, name)

    def events_for_pod_id(self, pod_entity_id: str) -> list[dict[str, Any]]:
        event_ids = {
            str(e["target_id"])
            for e in self.edges
            if e.get("relation") == RelationType.HAS_EVENT.value
            and str(e.get("source_id")) == pod_entity_id
            and e.get("target_id")
        }
        return [self.entities[eid] for eid in event_ids if eid in self.entities]
