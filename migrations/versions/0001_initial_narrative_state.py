"""Esquema relacional inicial do estado narrativo Mythra.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-01
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria o esquema completo definido para a Fase 01."""
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "stories",
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("premise", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_stories_user_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stories_user_id", "stories", ["user_id"])
    op.create_table(
        "story_preferences",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("tone", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_story_preferences_story_id_stories", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", name="uq_story_preferences_story_id"),
    )
    op.create_table(
        "characters",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("personality", sa.Text(), nullable=True),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("fears", sa.Text(), nullable=True),
        sa.Column("beliefs", sa.Text(), nullable=True),
        sa.Column("emotional_state", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_characters_story_id_stories", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_characters_story_id_id"),
    )
    op.create_index("ix_characters_story_id", "characters", ["story_id"])
    op.create_table(
        "story_arcs",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_story_arcs_story_id_stories", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_story_arcs_story_id_id"),
    )
    op.create_index("ix_story_arcs_story_position", "story_arcs", ["story_id", "position"])
    op.create_table(
        "story_events",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=200), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_story_events_story_id_stories", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_story_events_story_id_id"),
    )
    op.create_index("ix_story_events_story_occurred_at", "story_events", ["story_id", "occurred_at"])
    op.create_table(
        "story_facts",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("predicate", sa.String(length=200), nullable=False),
        sa.Column("object", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_story_facts_story_id_stories", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "id", name="uq_story_facts_story_id_id"),
    )
    op.create_index("ix_story_facts_story_id", "story_facts", ["story_id"])
    op.create_table(
        "character_relationships",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_character_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("target_character_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(length=100), nullable=False),
        sa.Column("trust", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source_character_id <> target_character_id", name="ck_relationship_distinct_characters"),
        sa.CheckConstraint("trust >= -1.0 AND trust <= 1.0", name="ck_relationship_trust_range"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_character_relationships_story_id_stories", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "source_character_id"], ["characters.story_id", "characters.id"], name="fk_relationship_source_same_story", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "target_character_id"], ["characters.story_id", "characters.id"], name="fk_relationship_target_same_story", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "source_character_id", "target_character_id", name="uq_relationship_direction"),
    )
    op.create_index("ix_relationships_story_id", "character_relationships", ["story_id"])
    op.create_table(
        "chapters",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("arc_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_chapters_story_id_stories", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "arc_id"], ["story_arcs.story_id", "story_arcs.id"], name="fk_chapters_arc_same_story", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chapters_story_arc_position", "chapters", ["story_id", "arc_id", "position"])
    op.create_table(
        "timeline_events",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_timeline_events_story_id_stories", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_timeline_events_story_occurred_at", "timeline_events", ["story_id", "occurred_at"])
    op.create_table(
        "plot_threads",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('open', 'resolved', 'abandoned')", name="ck_plot_thread_status"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name="fk_plot_threads_story_id_stories", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plot_threads_story_id", "plot_threads", ["story_id"])
    op.create_table(
        "character_knowledge",
        sa.Column("story_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("character_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("fact_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("visibility", sa.String(length=100), nullable=False),
        sa.Column("source_event_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_knowledge_confidence_range"),
        sa.ForeignKeyConstraint(["story_id", "character_id"], ["characters.story_id", "characters.id"], name="fk_knowledge_character_same_story", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "fact_id"], ["story_facts.story_id", "story_facts.id"], name="fk_knowledge_fact_same_story", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id", "source_event_id"], ["story_events.story_id", "story_events.id"], name="fk_knowledge_event_same_story", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "fact_id", name="uq_character_knowledge_character_fact"),
    )
    op.create_index("ix_character_knowledge_character_id", "character_knowledge", ["character_id"])
    op.create_index("ix_character_knowledge_fact_id", "character_knowledge", ["fact_id"])


def downgrade() -> None:
    """Remove o esquema completo criado pela migration inicial."""
    op.drop_index("ix_character_knowledge_fact_id", table_name="character_knowledge")
    op.drop_index("ix_character_knowledge_character_id", table_name="character_knowledge")
    op.drop_table("character_knowledge")
    op.drop_index("ix_plot_threads_story_id", table_name="plot_threads")
    op.drop_table("plot_threads")
    op.drop_index("ix_timeline_events_story_occurred_at", table_name="timeline_events")
    op.drop_table("timeline_events")
    op.drop_index("ix_chapters_story_arc_position", table_name="chapters")
    op.drop_table("chapters")
    op.drop_index("ix_relationships_story_id", table_name="character_relationships")
    op.drop_table("character_relationships")
    op.drop_index("ix_story_facts_story_id", table_name="story_facts")
    op.drop_table("story_facts")
    op.drop_index("ix_story_events_story_occurred_at", table_name="story_events")
    op.drop_table("story_events")
    op.drop_index("ix_story_arcs_story_position", table_name="story_arcs")
    op.drop_table("story_arcs")
    op.drop_index("ix_characters_story_id", table_name="characters")
    op.drop_table("characters")
    op.drop_table("story_preferences")
    op.drop_index("ix_stories_user_id", table_name="stories")
    op.drop_table("stories")
    op.drop_table("users")
