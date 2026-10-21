"""Cria memories (memória semântica, sem vínculo canônico).

Revision ID: 0009_memories
Revises: 0008_validation
Create Date: 2026-10-21
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_memories"
down_revision: str | None = "0008_validation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria memórias semânticas; não há FK para fatos ou conhecimento canônico."""
    op.create_table(
        "memories",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("character_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("memory_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("source_event_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("generation_run_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)", name="ck_memories_confidence_range"),
        sa.CheckConstraint("status IN ('active', 'superseded', 'rejected')", name="ck_memories_status"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_memories_story_id_stories", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "character_id"], ["characters.story_id", "characters.id"], name="fk_memories_character_same_story", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "source_event_id"], ["story_events.story_id", "story_events.id"], name="fk_memories_source_event_same_story"),
        sa.ForeignKeyConstraint(["story_id", "generation_run_id"], ["generation_runs.story_id", "generation_runs.id"], name="fk_memories_generation_run_same_story"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memories_story_character_status_created",
        "memories",
        ["story_id", "character_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_memories_story_character_status_created", table_name="memories")
    op.drop_table("memories")
