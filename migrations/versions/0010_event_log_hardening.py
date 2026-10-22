"""Endurece o log de eventos: origem, operação, imutabilidade e vínculo com transições.

Revision ID: 0010_event_log_hardening
Revises: 0009_memories
Create Date: 2026-10-21
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_event_log_hardening"
down_revision: str | None = "0009_memories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_FUNCTION = """
CREATE FUNCTION story_events_forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        -- Eventos só desaparecem junto com a própria história (ON DELETE CASCADE).
        IF NOT EXISTS (SELECT 1 FROM stories WHERE id = OLD.story_id) THEN
            RETURN OLD;
        END IF;
    END IF;
    RAISE EXCEPTION USING
        MESSAGE = 'story_events é append-only: ' || TG_OP || ' não é permitido',
        ERRCODE = 'integrity_constraint_violation';
END
$$
"""

APPLIED_EVENT_FUNCTION = """
CREATE FUNCTION state_transitions_check_applied_event() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    ev story_events;
    expected_source text;
BEGIN
    IF NEW.applied_story_event_id IS NULL THEN
        RETURN NEW;
    END IF;
    expected_source := CASE WHEN NEW.generation_run_id IS NOT NULL THEN 'generation' ELSE 'user' END;
    SELECT * INTO ev FROM story_events
    WHERE id = NEW.applied_story_event_id AND story_id = NEW.story_id;
    IF NOT FOUND
        OR ev.event_type <> NEW.event_type
        OR ev.aggregate_type <> NEW.aggregate_type
        OR ev.aggregate_id IS DISTINCT FROM NEW.aggregate_id
        OR ev.source <> expected_source
    THEN
        RAISE EXCEPTION 'o evento aplicado não corresponde à transição'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END
$$
"""

OPERATION_BACKFILL = """
UPDATE story_events SET operation = CASE event_type
    WHEN 'canonical_fact_created' THEN 'create_fact'
    WHEN 'canonical_fact_updated' THEN 'update_fact'
    WHEN 'character_state_updated' THEN 'update_character'
    WHEN 'relationship_updated' THEN 'update_relationship'
    WHEN 'character_knowledge_updated' THEN 'update_knowledge'
    WHEN 'timeline_event_updated' THEN 'update_timeline_event'
    WHEN 'plot_thread_updated' THEN 'update_plot_thread'
    WHEN 'story_arc_updated' THEN 'update_arc'
    WHEN 'chapter_updated' THEN 'update_chapter'
    ELSE 'record_story_event'
END
"""


def upgrade() -> None:
    """Adiciona origem/operação, índice de leitura e triggers de integridade do histórico."""
    op.add_column("story_events", sa.Column("source", sa.String(length=20), nullable=True))
    op.add_column("story_events", sa.Column("operation", sa.String(length=100), nullable=True))
    # Todo evento anterior nasceu de uma chamada à API (ação de usuário); não havia origem registrada.
    op.execute("UPDATE story_events SET source = 'user'")
    op.execute(OPERATION_BACKFILL)
    op.alter_column("story_events", "source", nullable=False)
    op.alter_column("story_events", "operation", nullable=False)
    op.create_check_constraint(
        "ck_story_events_source", "story_events", "source IN ('user', 'system', 'generation')"
    )
    op.create_index("ix_story_events_story_id_sequence", "story_events", ["story_id", "sequence"])

    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER trg_story_events_append_only BEFORE UPDATE OR DELETE ON story_events "
        "FOR EACH ROW EXECUTE FUNCTION story_events_forbid_mutation()"
    )
    op.execute(
        "CREATE TRIGGER trg_story_events_no_truncate BEFORE TRUNCATE ON story_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION story_events_forbid_mutation()"
    )

    op.execute(APPLIED_EVENT_FUNCTION)
    op.execute(
        "CREATE TRIGGER trg_state_transitions_applied_event BEFORE INSERT OR UPDATE "
        "ON state_transitions FOR EACH ROW EXECUTE FUNCTION state_transitions_check_applied_event()"
    )


def downgrade() -> None:
    """Remove triggers antes das colunas; os valores de origem/operação são descartados."""
    op.execute("DROP TRIGGER trg_state_transitions_applied_event ON state_transitions")
    op.execute("DROP FUNCTION state_transitions_check_applied_event()")
    op.execute("DROP TRIGGER trg_story_events_no_truncate ON story_events")
    op.execute("DROP TRIGGER trg_story_events_append_only ON story_events")
    op.execute("DROP FUNCTION story_events_forbid_mutation()")
    op.drop_index("ix_story_events_story_id_sequence", table_name="story_events")
    op.drop_constraint("ck_story_events_source", "story_events", type_="check")
    op.drop_column("story_events", "operation")
    op.drop_column("story_events", "source")
