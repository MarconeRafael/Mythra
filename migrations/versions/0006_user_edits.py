"""Cria user_edits.

Revision ID: 0006_user_edits
Revises: 0005_generation
Create Date: 2026-10-21
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_user_edits"
down_revision: str | None = "0005_generation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria a auditoria imutável de edições de texto do usuário."""
    op.create_table(
        "user_edits",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("chapter_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("scene_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("resulting_revision", sa.Integer(), nullable=False),
        sa.Column("content_before", sa.Text(), nullable=False),
        sa.Column("content_after", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("num_nonnulls(chapter_id, scene_id) = 1", name="ck_user_edits_single_target"),
        sa.CheckConstraint("resulting_revision > base_revision", name="ck_user_edits_revision_increases"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_user_edits_story_id_stories", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_edits_user_id_users"),
        sa.ForeignKeyConstraint(["story_id", "chapter_id"], ["chapters.story_id", "chapters.id"], name="fk_user_edits_chapter_same_story"),
        sa.ForeignKeyConstraint(["story_id", "scene_id"], ["scenes.story_id", "scenes.id"], name="fk_user_edits_scene_same_story"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_user_edits_story_id_id"),
    )
    op.create_index("ix_user_edits_story_id_created_at", "user_edits", ["story_id", "created_at"])
    op.create_index(
        "ix_user_edits_chapter_id_resulting_revision",
        "user_edits",
        ["chapter_id", "resulting_revision"],
        postgresql_where=sa.text("chapter_id IS NOT NULL"),
    )
    op.create_index(
        "ix_user_edits_scene_id_resulting_revision",
        "user_edits",
        ["scene_id", "resulting_revision"],
        postgresql_where=sa.text("scene_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_user_edits_scene_id_resulting_revision", table_name="user_edits")
    op.drop_index("ix_user_edits_chapter_id_resulting_revision", table_name="user_edits")
    op.drop_index("ix_user_edits_story_id_created_at", table_name="user_edits")
    op.drop_table("user_edits")
