"""Cria validation_runs e validation_results.

Revision ID: 0008_validation
Revises: 0007_state_transitions
Create Date: 2026-10-21
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_validation"
down_revision: str | None = "0007_state_transitions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria o histórico de validações de rascunhos e edições."""
    op.create_table(
        "validation_runs",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("generation_run_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("user_edit_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("validator", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("base_state_version", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("num_nonnulls(generation_run_id, user_edit_id) = 1", name="ck_validation_runs_single_subject"),
        sa.CheckConstraint("status IN ('pending', 'running', 'passed', 'failed', 'error')", name="ck_validation_runs_status"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_validation_runs_story_id_stories", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "generation_run_id"], ["generation_runs.story_id", "generation_runs.id"], name="fk_validation_runs_generation_run_same_story"),
        sa.ForeignKeyConstraint(["story_id", "user_edit_id"], ["user_edits.story_id", "user_edits.id"], name="fk_validation_runs_user_edit_same_story"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_validation_runs_story_id_id"),
    )
    op.create_index("ix_validation_runs_story_id_created_at", "validation_runs", ["story_id", "created_at"])
    op.create_index(
        "ix_validation_runs_generation_run_id",
        "validation_runs",
        ["generation_run_id"],
        postgresql_where=sa.text("generation_run_id IS NOT NULL"),
    )
    op.create_index(
        "ix_validation_runs_user_edit_id",
        "validation_runs",
        ["user_edit_id"],
        postgresql_where=sa.text("user_edit_id IS NOT NULL"),
    )

    op.create_table(
        "validation_results",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("validation_run_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("narrative_rule_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("state_transition_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("scene_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("severity IN ('info', 'warning', 'error')", name="ck_validation_results_severity"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_validation_results_story_id_stories", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "validation_run_id"], ["validation_runs.story_id", "validation_runs.id"], name="fk_validation_results_run_same_story", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "narrative_rule_id"], ["narrative_rules.story_id", "narrative_rules.id"], name="fk_validation_results_rule_same_story"),
        sa.ForeignKeyConstraint(["story_id", "state_transition_id"], ["state_transitions.story_id", "state_transitions.id"], name="fk_validation_results_transition_same_story"),
        sa.ForeignKeyConstraint(["story_id", "scene_id"], ["scenes.story_id", "scenes.id"], name="fk_validation_results_scene_same_story"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_validation_results_validation_run_id", "validation_results", ["validation_run_id"])
    op.create_index("ix_validation_results_story_id", "validation_results", ["story_id"])


def downgrade() -> None:
    op.drop_index("ix_validation_results_story_id", table_name="validation_results")
    op.drop_index("ix_validation_results_validation_run_id", table_name="validation_results")
    op.drop_table("validation_results")
    op.drop_index("ix_validation_runs_user_edit_id", table_name="validation_runs")
    op.drop_index("ix_validation_runs_generation_run_id", table_name="validation_runs")
    op.drop_index("ix_validation_runs_story_id_created_at", table_name="validation_runs")
    op.drop_table("validation_runs")
