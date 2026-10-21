"""Entidades de mundo, cenas, regras narrativas e memórias semânticas."""

from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mythra.infrastructure.db.base import Base
from mythra.infrastructure.db.models.narrative import TimestampMixin


class Location(TimestampMixin, Base):
    """Lugar da história, com hierarquia opcional dentro da mesma história."""

    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_locations_story_id_id"),
        ForeignKeyConstraint(
            ["story_id", "parent_location_id"],
            ["locations.story_id", "locations.id"],
            name="fk_locations_parent_same_story",
        ),
        CheckConstraint(
            "parent_location_id IS NULL OR parent_location_id <> id",
            name="ck_locations_not_own_parent",
        ),
        Index("ix_locations_story_id", "story_id"),
        Index("ix_locations_story_id_parent_location_id", "story_id", "parent_location_id"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    parent_location_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_type: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Faction(TimestampMixin, Base):
    """Grupo ou organização da história."""

    __tablename__ = "factions"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_factions_story_id_id"),
        Index("uq_factions_story_id_lower_name", "story_id", text("lower(name)"), unique=True),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Scene(TimestampMixin, Base):
    """Cena ordenada de um capítulo; unidade editável de texto narrativo."""

    __tablename__ = "scenes"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_scenes_story_id_id"),
        UniqueConstraint(
            "chapter_id",
            "position",
            name="uq_scenes_chapter_id_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["story_id", "chapter_id"],
            ["chapters.story_id", "chapters.id"],
            name="fk_scenes_chapter_same_story",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["story_id", "location_id"],
            ["locations.story_id", "locations.id"],
            name="fk_scenes_location_same_story",
        ),
        ForeignKeyConstraint(
            ["story_id", "timeline_event_id"],
            ["timeline_events.story_id", "timeline_events.id"],
            name="fk_scenes_timeline_event_same_story",
        ),
        ForeignKeyConstraint(
            ["story_id", "generation_run_id"],
            ["generation_runs.story_id", "generation_runs.id"],
            name="fk_scenes_generation_run_same_story",
        ),
        CheckConstraint("position >= 1", name="ck_scenes_position_positive"),
        CheckConstraint("revision >= 1", name="ck_scenes_revision_positive"),
        Index("ix_scenes_story_id", "story_id"),
        Index(
            "ix_scenes_generation_run_id",
            "generation_run_id",
            postgresql_where=text("generation_run_id IS NOT NULL"),
        ),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    location_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    timeline_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    generation_run_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class NarrativeRule(TimestampMixin, Base):
    """Regra de mundo ou continuidade consumida pela validação."""

    __tablename__ = "narrative_rules"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_narrative_rules_story_id_id"),
        CheckConstraint(
            "severity IN ('info', 'warning', 'error')", name="ck_narrative_rules_severity"
        ),
        Index("ix_narrative_rules_story_id", "story_id"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    definition: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class Memory(TimestampMixin, Base):
    """Memória semântica: interpretação ou resumo que nunca é fato canônico por si só."""

    __tablename__ = "memories"
    __table_args__ = (
        ForeignKeyConstraint(
            ["story_id", "character_id"],
            ["characters.story_id", "characters.id"],
            name="fk_memories_character_same_story",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["story_id", "source_event_id"],
            ["story_events.story_id", "story_events.id"],
            name="fk_memories_source_event_same_story",
        ),
        ForeignKeyConstraint(
            ["story_id", "generation_run_id"],
            ["generation_runs.story_id", "generation_runs.id"],
            name="fk_memories_generation_run_same_story",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_memories_confidence_range",
        ),
        CheckConstraint(
            "status IN ('active', 'superseded', 'rejected')", name="ck_memories_status"
        ),
        Index(
            "ix_memories_story_character_status_created",
            "story_id",
            "character_id",
            "status",
            "created_at",
        ),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    character_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    source_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    generation_run_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
