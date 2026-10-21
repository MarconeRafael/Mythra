"""Cria narrative_rules.

Revision ID: 0004_narrative_rules
Revises: 0003_world_and_scenes
Create Date: 2026-10-21
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_narrative_rules"
down_revision: str | None = "0003_world_and_scenes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria as regras de mundo e continuidade consumidas pela validação."""
    op.create_table(
        "narrative_rules",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("rule_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("severity IN ('info', 'warning', 'error')", name="ck_narrative_rules_severity"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_narrative_rules_story_id_stories", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_narrative_rules_story_id_id"),
    )
    op.create_index("ix_narrative_rules_story_id", "narrative_rules", ["story_id"])


def downgrade() -> None:
    op.drop_index("ix_narrative_rules_story_id", table_name="narrative_rules")
    op.drop_table("narrative_rules")
