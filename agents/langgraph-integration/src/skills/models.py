"""Skill typed contracts."""

from __future__ import annotations

from typing import TypedDict


class SkillMatch(TypedDict):
    name: str
    symptom: str
    summary: str
    fingerprint: str
    path: str
    score: float
    hit_count: int
    source_count: int
    verified: bool


class SkillRecord(TypedDict, total=False):
    name: str
    symptom: str
    summary: str
    fingerprint: str
    path: str
    hit_count: int
    source_count: int
    verified: bool
    issues: list[str]
    recommended_actions: list[str]
    body: str
    markdown: str


class SkillUpsertResult(TypedDict):
    fingerprint: str
    path: str
    created: bool
    hit_count: int
    source_count: int
