"""Cria locations, factions e scenes.

Revision ID: 0003_world_and_scenes
Revises: 0002_integrity_hardening
Create Date: 2026-10-21
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_world_and_scenes"
down_revision: str | None = "0002_integrity_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_and_timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    """Cria as entidades de mundo e a unidade de texto editável."""
    op.create_table(
        "locations",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("parent_location_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location_type", sa.String(length=100), nullable=True),
        *_identity_and_timestamps(),
        sa.CheckConstraint("parent_location_id IS NULL OR parent_location_id <> id", name="ck_locations_not_own_parent"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_locations_story_id_stories", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "parent_location_id"], ["locations.story_id", "locations.id"], name="fk_locations_parent_same_story"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_locations_story_id_id"),
    )
    op.create_index("ix_locations_story_id", "locations", ["story_id"])
    op.create_index("ix_locations_story_id_parent_location_id", "locations", ["story_id", "parent_location_id"])

    op.create_table(
        "factions",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_identity_and_timestamps(),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_factions_story_id_stories", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_factions_story_id_id"),
    )
    op.create_index("uq_factions_story_id_lower_name", "factions", ["story_id", sa.text("lower(name)")], unique=True)

    op.create_table(
        "scenes",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("chapter_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("location_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("timeline_event_id", sa.Uuid(as_uuid=True), nullable=True),
        *_identity_and_timestamps(),
        sa.CheckConstraint("position >= 1", name="ck_scenes_position_positive"),
        sa.CheckConstraint("revision >= 1", name="ck_scenes_revision_positive"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_scenes_story_id_stories", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "chapter_id"], ["chapters.story_id", "chapters.id"], name="fk_scenes_chapter_same_story", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "location_id"], ["locations.story_id", "locations.id"], name="fk_scenes_location_same_story"),
        sa.ForeignKeyConstraint(["story_id", "timeline_event_id"], ["timeline_events.story_id", "timeline_events.id"], name="fk_scenes_timeline_event_same_story"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_scenes_story_id_id"),
        sa.UniqueConstraint("chapter_id", "position", name="uq_scenes_chapter_id_position", deferrable=True, initially="DEFERRED"),
    )
    op.create_index("ix_scenes_story_id", "scenes", ["story_id"])


def downgrade() -> None:
    """Remove as tabelas na ordem inversa das dependências."""
    op.drop_index("ix_scenes_story_id", table_name="scenes")
    op.drop_table("scenes")
    op.drop_index("uq_factions_story_id_lower_name", table_name="factions")
    op.drop_table("factions")
    op.drop_index("ix_locations_story_id_parent_location_id", table_name="locations")
    op.drop_index("ix_locations_story_id", table_name="locations")
    op.drop_table("locations")
