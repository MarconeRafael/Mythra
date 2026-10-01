"""Tabelas relacionais para estado narrativo canônico e histórico de eventos."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mythra.infrastructure.db.base import Base


class IdCreatedMixin:
    """Campos comuns a registros imutáveis ou append-only."""

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class TimestampMixin(IdCreatedMixin):
    """Identificador e timestamps de criação/atualização de estado mutável."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class User(TimestampMixin, Base):
    """Proprietário das histórias persistidas."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)


class Story(TimestampMixin, Base):
    """História persistente cujo estado canônico está em tabelas relacionais."""

    __tablename__ = "stories"
    __table_args__ = (Index("ix_stories_user_id", "user_id"),)

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    premise: Mapped[str] = mapped_column(Text, nullable=False)


class StoryPreferences(TimestampMixin, Base):
    """Preferências configuráveis em relação um-para-um com uma história."""

    __tablename__ = "story_preferences"
    __table_args__ = (UniqueConstraint("story_id", name="uq_story_preferences_story_id"),)

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    tone: Mapped[str] = mapped_column(Text, nullable=False)


class Character(TimestampMixin, Base):
    """Estado atual de uma personagem pertencente a uma história."""

    __tablename__ = "characters"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_characters_story_id_id"),
        Index("ix_characters_story_id", "story_id"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    fears: Mapped[str | None] = mapped_column(Text, nullable=True)
    beliefs: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotional_state: Mapped[str | None] = mapped_column(Text, nullable=True)


class CharacterRelationship(TimestampMixin, Base):
    """Relação direcionada atual entre personagens de uma mesma história."""

    __tablename__ = "character_relationships"
    __table_args__ = (
        UniqueConstraint(
            "story_id",
            "source_character_id",
            "target_character_id",
            name="uq_relationship_direction",
        ),
        ForeignKeyConstraint(
            ["story_id", "source_character_id"],
            ["characters.story_id", "characters.id"],
            name="fk_relationship_source_same_story",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["story_id", "target_character_id"],
            ["characters.story_id", "characters.id"],
            name="fk_relationship_target_same_story",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "source_character_id <> target_character_id",
            name="ck_relationship_distinct_characters",
        ),
        CheckConstraint("trust >= -1.0 AND trust <= 1.0", name="ck_relationship_trust_range"),
        Index("ix_relationships_story_id", "story_id"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    source_character_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    target_character_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    trust: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False)


class StoryFact(TimestampMixin, Base):
    """Fato narrativo estruturado e independente do conhecimento individual."""

    __tablename__ = "story_facts"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_story_facts_story_id_id"),
        Index("ix_story_facts_story_id", "story_id"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    predicate: Mapped[str] = mapped_column(String(200), nullable=False)
    object: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)


class CharacterKnowledge(TimestampMixin, Base):
    """Conhecimento de uma personagem sobre um fato e evento de origem."""

    __tablename__ = "character_knowledge"
    __table_args__ = (
        UniqueConstraint("character_id", "fact_id", name="uq_character_knowledge_character_fact"),
        ForeignKeyConstraint(
            ["story_id", "character_id"],
            ["characters.story_id", "characters.id"],
            name="fk_knowledge_character_same_story",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["story_id", "fact_id"],
            ["story_facts.story_id", "story_facts.id"],
            name="fk_knowledge_fact_same_story",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["story_id", "source_event_id"],
            ["story_events.story_id", "story_events.id"],
            name="fk_knowledge_event_same_story",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_knowledge_confidence_range",
        ),
        Index("ix_character_knowledge_character_id", "character_id"),
        Index("ix_character_knowledge_fact_id", "fact_id"),
    )

    story_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    character_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    fact_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    visibility: Mapped[str] = mapped_column(String(100), nullable=False)
    source_event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


class StoryArc(TimestampMixin, Base):
    """Arco narrativo ordenado dentro de uma história."""

    __tablename__ = "story_arcs"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_story_arcs_story_id_id"),
        Index("ix_story_arcs_story_position", "story_id", "position"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False)


class Chapter(TimestampMixin, Base):
    """Conteúdo persistido que pertence ao mesmo tempo a uma história e arco."""

    __tablename__ = "chapters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["story_id", "arc_id"],
            ["story_arcs.story_id", "story_arcs.id"],
            name="fk_chapters_arc_same_story",
            ondelete="CASCADE",
        ),
        Index("ix_chapters_story_arc_position", "story_id", "arc_id", "position"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    arc_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False)


class TimelineEvent(TimestampMixin, Base):
    """Evento temporal ordenado por instante ocorrido, não por ID de linha."""

    __tablename__ = "timeline_events"
    __table_args__ = (Index("ix_timeline_events_story_occurred_at", "story_id", "occurred_at"),)

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlotThread(TimestampMixin, Base):
    """Linha narrativa aberta com estado explícito controlado."""

    __tablename__ = "plot_threads"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'resolved', 'abandoned')",
            name="ck_plot_thread_status",
        ),
        Index("ix_plot_threads_story_id", "story_id"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class StoryEvent(IdCreatedMixin, Base):
    """Registro histórico append-only dos acontecimentos relevantes."""

    __tablename__ = "story_events"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_story_events_story_id_id"),
        Index("ix_story_events_story_occurred_at", "story_id", "occurred_at"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(200), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
