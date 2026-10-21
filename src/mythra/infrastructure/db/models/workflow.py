"""Geração, validação, edições do usuário e propostas de transição de estado canônico."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
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
from mythra.infrastructure.db.models.narrative import IdCreatedMixin, TimestampMixin


class GenerationRun(TimestampMixin, Base):
    """Execução de geração e a versão do estado canônico em que se baseou."""

    __tablename__ = "generation_runs"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_generation_runs_story_id_id"),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_generation_runs_status",
        ),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_generation_runs_finished_after_started",
        ),
        Index("ix_generation_runs_story_id_created_at", "story_id", "created_at"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    base_state_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    context_manifest: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GenerationEvent(IdCreatedMixin, Base):
    """Passo append-only de uma execução de geração."""

    __tablename__ = "generation_events"
    __table_args__ = (
        UniqueConstraint(
            "generation_run_id", "sequence", name="uq_generation_events_generation_run_id_sequence"
        ),
        ForeignKeyConstraint(
            ["story_id", "generation_run_id"],
            ["generation_runs.story_id", "generation_runs.id"],
            name="fk_generation_events_run_same_story",
            ondelete="CASCADE",
        ),
        CheckConstraint("sequence >= 1", name="ck_generation_events_sequence_positive"),
        Index("ix_generation_events_story_id", "story_id"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    generation_run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserEdit(IdCreatedMixin, Base):
    """Auditoria imutável de uma edição de texto feita pelo usuário."""

    __tablename__ = "user_edits"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_user_edits_story_id_id"),
        ForeignKeyConstraint(
            ["story_id", "chapter_id"],
            ["chapters.story_id", "chapters.id"],
            name="fk_user_edits_chapter_same_story",
        ),
        ForeignKeyConstraint(
            ["story_id", "scene_id"],
            ["scenes.story_id", "scenes.id"],
            name="fk_user_edits_scene_same_story",
        ),
        CheckConstraint(
            "num_nonnulls(chapter_id, scene_id) = 1", name="ck_user_edits_single_target"
        ),
        CheckConstraint(
            "resulting_revision > base_revision", name="ck_user_edits_revision_increases"
        ),
        Index("ix_user_edits_story_id_created_at", "story_id", "created_at"),
        Index(
            "ix_user_edits_chapter_id_resulting_revision",
            "chapter_id",
            "resulting_revision",
            postgresql_where=text("chapter_id IS NOT NULL"),
        ),
        Index(
            "ix_user_edits_scene_id_resulting_revision",
            "scene_id",
            "resulting_revision",
            postgresql_where=text("scene_id IS NOT NULL"),
        ),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    chapter_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    scene_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content_before: Mapped[str] = mapped_column(Text, nullable=False)
    content_after: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class StateTransition(TimestampMixin, Base):
    """Proposta de mudança canônica; só altera estado ao ser aplicada por caso de uso."""

    __tablename__ = "state_transitions"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_state_transitions_story_id_id"),
        ForeignKeyConstraint(
            ["story_id", "generation_run_id"],
            ["generation_runs.story_id", "generation_runs.id"],
            name="fk_state_transitions_generation_run_same_story",
        ),
        ForeignKeyConstraint(
            ["story_id", "user_edit_id"],
            ["user_edits.story_id", "user_edits.id"],
            name="fk_state_transitions_user_edit_same_story",
        ),
        ForeignKeyConstraint(
            ["story_id", "applied_story_event_id"],
            ["story_events.story_id", "story_events.id"],
            name="fk_state_transitions_applied_event_same_story",
        ),
        CheckConstraint(
            "num_nonnulls(generation_run_id, user_edit_id) = 1",
            name="ck_state_transitions_single_origin",
        ),
        CheckConstraint(
            "operation IN ('create', 'update')", name="ck_state_transitions_operation"
        ),
        CheckConstraint(
            "operation <> 'update' OR aggregate_id IS NOT NULL",
            name="ck_state_transitions_update_has_aggregate",
        ),
        CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected', 'applied', 'stale')",
            name="ck_state_transitions_status",
        ),
        CheckConstraint(
            "status <> 'applied' OR "
            "(applied_at IS NOT NULL AND applied_story_event_id IS NOT NULL)",
            name="ck_state_transitions_applied_has_event",
        ),
        CheckConstraint(
            "applied_story_event_id IS NULL OR status = 'applied'",
            name="ck_state_transitions_event_only_when_applied",
        ),
        CheckConstraint(
            "status NOT IN ('approved', 'rejected', 'applied') OR decided_at IS NOT NULL",
            name="ck_state_transitions_decided_has_timestamp",
        ),
        Index(
            "uq_state_transitions_applied_story_event_id",
            "applied_story_event_id",
            unique=True,
            postgresql_where=text("applied_story_event_id IS NOT NULL"),
        ),
        Index(
            "ix_state_transitions_story_id_status_created_at",
            "story_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_state_transitions_proposed",
            "story_id",
            "created_at",
            postgresql_where=text("status = 'proposed'"),
        ),
        Index(
            "ix_state_transitions_aggregate",
            "story_id",
            "aggregate_type",
            "aggregate_id",
        ),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    generation_run_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    user_edit_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    operation: Mapped[str] = mapped_column(String(10), nullable=False)
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    base_state_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="proposed", server_default="proposed"
    )
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_story_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class ValidationRun(TimestampMixin, Base):
    """Validação de um rascunho gerado ou de uma edição do usuário."""

    __tablename__ = "validation_runs"
    __table_args__ = (
        UniqueConstraint("story_id", "id", name="uq_validation_runs_story_id_id"),
        ForeignKeyConstraint(
            ["story_id", "generation_run_id"],
            ["generation_runs.story_id", "generation_runs.id"],
            name="fk_validation_runs_generation_run_same_story",
        ),
        ForeignKeyConstraint(
            ["story_id", "user_edit_id"],
            ["user_edits.story_id", "user_edits.id"],
            name="fk_validation_runs_user_edit_same_story",
        ),
        CheckConstraint(
            "num_nonnulls(generation_run_id, user_edit_id) = 1",
            name="ck_validation_runs_single_subject",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'passed', 'failed', 'error')",
            name="ck_validation_runs_status",
        ),
        Index("ix_validation_runs_story_id_created_at", "story_id", "created_at"),
        Index(
            "ix_validation_runs_generation_run_id",
            "generation_run_id",
            postgresql_where=text("generation_run_id IS NOT NULL"),
        ),
        Index(
            "ix_validation_runs_user_edit_id",
            "user_edit_id",
            postgresql_where=text("user_edit_id IS NOT NULL"),
        ),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    generation_run_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    user_edit_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    validator: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    base_state_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ValidationResult(IdCreatedMixin, Base):
    """Achado imutável produzido por uma validação."""

    __tablename__ = "validation_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["story_id", "validation_run_id"],
            ["validation_runs.story_id", "validation_runs.id"],
            name="fk_validation_results_run_same_story",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["story_id", "narrative_rule_id"],
            ["narrative_rules.story_id", "narrative_rules.id"],
            name="fk_validation_results_rule_same_story",
        ),
        ForeignKeyConstraint(
            ["story_id", "state_transition_id"],
            ["state_transitions.story_id", "state_transitions.id"],
            name="fk_validation_results_transition_same_story",
        ),
        ForeignKeyConstraint(
            ["story_id", "scene_id"],
            ["scenes.story_id", "scenes.id"],
            name="fk_validation_results_scene_same_story",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'error')", name="ck_validation_results_severity"
        ),
        Index("ix_validation_results_validation_run_id", "validation_run_id"),
        Index("ix_validation_results_story_id", "story_id"),
    )

    story_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    validation_run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    narrative_rule_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    state_transition_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    scene_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
