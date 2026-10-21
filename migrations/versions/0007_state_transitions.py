"""Cria state_transitions, a área de proposta de mudanças canônicas.

Revision ID: 0007_state_transitions
Revises: 0006_user_edits
Create Date: 2026-10-21
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_state_transitions"
down_revision: str | None = "0006_user_edits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria propostas que só alteram estado canônico quando aplicadas por caso de uso."""
    op.create_table(
        "state_transitions",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("generation_run_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("user_edit_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=200), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("operation", sa.String(length=10), nullable=False),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("base_state_version", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="proposed", nullable=False),
        sa.Column("decided_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_story_event_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("num_nonnulls(generation_run_id, user_edit_id) = 1", name="ck_state_transitions_single_origin"),
        sa.CheckConstraint("operation IN ('create', 'update')", name="ck_state_transitions_operation"),
        sa.CheckConstraint("operation <> 'update' OR aggregate_id IS NOT NULL", name="ck_state_transitions_update_has_aggregate"),
        sa.CheckConstraint("status IN ('proposed', 'approved', 'rejected', 'applied', 'stale')", name="ck_state_transitions_status"),
        sa.CheckConstraint("status <> 'applied' OR (applied_at IS NOT NULL AND applied_story_event_id IS NOT NULL)", name="ck_state_transitions_applied_has_event"),
        sa.CheckConstraint("applied_story_event_id IS NULL OR status = 'applied'", name="ck_state_transitions_event_only_when_applied"),
        sa.CheckConstraint("status NOT IN ('approved', 'rejected', 'applied') OR decided_at IS NOT NULL", name="ck_state_transitions_decided_has_timestamp"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_state_transitions_story_id_stories", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], name="fk_state_transitions_decided_by_user_id_users"),
        sa.ForeignKeyConstraint(["story_id", "generation_run_id"], ["generation_runs.story_id", "generation_runs.id"], name="fk_state_transitions_generation_run_same_story"),
        sa.ForeignKeyConstraint(["story_id", "user_edit_id"], ["user_edits.story_id", "user_edits.id"], name="fk_state_transitions_user_edit_same_story"),
        sa.ForeignKeyConstraint(["story_id", "applied_story_event_id"], ["story_events.story_id", "story_events.id"], name="fk_state_transitions_applied_event_same_story"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_state_transitions_story_id_id"),
    )
    op.create_index(
        "uq_state_transitions_applied_story_event_id",
        "state_transitions",
        ["applied_story_event_id"],
        unique=True,
        postgresql_where=sa.text("applied_story_event_id IS NOT NULL"),
    )
    op.create_index("ix_state_transitions_story_id_status_created_at", "state_transitions", ["story_id", "status", "created_at"])
    op.create_index(
        "ix_state_transitions_proposed",
        "state_transitions",
        ["story_id", "created_at"],
        postgresql_where=sa.text("status = 'proposed'"),
    )
    op.create_index("ix_state_transitions_aggregate", "state_transitions", ["story_id", "aggregate_type", "aggregate_id"])


def downgrade() -> None:
    op.drop_index("ix_state_transitions_aggregate", table_name="state_transitions")
    op.drop_index("ix_state_transitions_proposed", table_name="state_transitions")
    op.drop_index("ix_state_transitions_story_id_status_created_at", table_name="state_transitions")
    op.drop_index("uq_state_transitions_applied_story_event_id", table_name="state_transitions")
    op.drop_table("state_transitions")
