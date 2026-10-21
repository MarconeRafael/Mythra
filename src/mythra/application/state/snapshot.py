"""Snapshot tipado e imutável do estado canônico atual de uma história.

Contém apenas estado atual normalizado; o histórico imutável de StoryEvents é
uma consulta separada (`EventUseCases.list_story_events`).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class StorySnapshot:
    id: UUID
    user_id: UUID
    title: str
    premise: str


@dataclass(frozen=True)
class PreferencesSnapshot:
    tone: str


@dataclass(frozen=True)
class CharacterSnapshot:
    id: UUID
    name: str
    description: str | None
    age: int | None
    personality: str | None
    goals: str | None
    fears: str | None
    beliefs: str | None
    emotional_state: str | None


@dataclass(frozen=True)
class RelationshipSnapshot:
    id: UUID
    source_character_id: UUID
    target_character_id: UUID
    relationship_type: str
    trust: float
    status: str


@dataclass(frozen=True)
class FactSnapshot:
    id: UUID
    subject: str
    predicate: str
    object: str
    valid_from: datetime
    valid_to: datetime | None
    source: str


@dataclass(frozen=True)
class KnowledgeSnapshot:
    id: UUID
    character_id: UUID
    fact_id: UUID
    known_at: datetime
    confidence: float
    visibility: str
    source_event_id: UUID


@dataclass(frozen=True)
class TimelineEventSnapshot:
    id: UUID
    title: str
    description: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class PlotThreadSnapshot:
    id: UUID
    title: str
    description: str | None
    status: str


@dataclass(frozen=True)
class ArcSnapshot:
    id: UUID
    title: str
    description: str | None
    position: int
    status: str


@dataclass(frozen=True)
class ChapterSnapshot:
    id: UUID
    arc_id: UUID
    title: str
    position: int
    summary: str | None
    content: str | None
    status: str


@dataclass(frozen=True)
class StoryStateSnapshot:
    """Estado canônico atual; Locations e Factions seguem adiados da Fase 02."""

    story: StorySnapshot
    preferences: PreferencesSnapshot | None
    characters: tuple[CharacterSnapshot, ...]
    relationships: tuple[RelationshipSnapshot, ...]
    facts: tuple[FactSnapshot, ...]
    knowledge: tuple[KnowledgeSnapshot, ...]
    timeline_events: tuple[TimelineEventSnapshot, ...]
    plot_threads: tuple[PlotThreadSnapshot, ...]
    arcs: tuple[ArcSnapshot, ...]
    chapters: tuple[ChapterSnapshot, ...]
