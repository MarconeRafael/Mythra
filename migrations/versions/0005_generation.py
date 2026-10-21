"""Cria generation_runs e generation_events e liga a procedência de capítulos e cenas.

Revision ID: 0005_generation
Revises: 0004_narrative_rules
Create Date: 2026-10-21
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_generation"
down_revision: str | None = "0004_narrative_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria o histórico de execuções de geração sem tocar em estado canônico."""
    op.create_table(
        "generation_runs",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("run_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("base_state_version", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("context_manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')", name="ck_generation_runs_status"),
        sa.CheckConstraint("finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at", name="ck_generation_runs_finished_after_started"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_generation_runs_story_id_stories", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], name="fk_generation_runs_requested_by_user_id_users"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_generation_runs_story_id_id"),
    )
    op.create_index("ix_generation_runs_story_id_created_at", "generation_runs", ["story_id", "created_at"])

    op.create_table(
        "generation_events",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("generation_run_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="ck_generation_events_sequence_positive"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_generation_events_story_id_stories", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "generation_run_id"], ["generation_runs.story_id", "generation_runs.id"], name="fk_generation_events_run_same_story", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generation_run_id", "sequence", name="uq_generation_events_generation_run_id_sequence"),
    )
    op.create_index("ix_generation_events_story_id", "generation_events", ["story_id"])

    for table in ("chapters", "scenes"):
        op.add_column(table, sa.Column("generation_run_id", sa.Uuid(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_generation_run_same_story",
            table,
            "generation_runs",
            ["story_id", "generation_run_id"],
            ["story_id", "id"],
        )
        op.create_index(
            f"ix_{table}_generation_run_id",
            table,
            ["generation_run_id"],
            postgresql_where=sa.text("generation_run_id IS NOT NULL"),
        )


def downgrade() -> None:
    for table in ("scenes", "chapters"):
        op.drop_index(f"ix_{table}_generation_run_id", table_name=table)
        op.drop_constraint(f"fk_{table}_generation_run_same_story", table, type_="foreignkey")
        op.drop_column(table, "generation_run_id")
    op.drop_index("ix_generation_events_story_id", table_name="generation_events")
    op.drop_table("generation_events")
    op.drop_index("ix_generation_runs_story_id_created_at", table_name="generation_runs")
    op.drop_table("generation_runs")
