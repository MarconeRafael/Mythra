"""Histórico de migrations: paridade com os modelos, SQL offline, dados existentes e downgrade."""

import io
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_models_and_head_revision_have_no_schema_drift(alembic_config: Config) -> None:
    command.check(alembic_config)


def test_offline_sql_generation_covers_all_new_revisions(postgres_url: str) -> None:
    buffer = io.StringIO()
    config = Config("alembic.ini", output_buffer=buffer)
    config.set_main_option("sqlalchemy.url", postgres_url.replace("%", "%%"))

    command.upgrade(config, "0001_initial:head", sql=True)

    sql = buffer.getvalue()
    for table in ("scenes", "state_transitions", "memories", "validation_results", "user_edits"):
        assert f"CREATE TABLE {table}" in sql


def test_existing_valid_data_survives_upgrade_and_downgrade_is_clean(
    alembic_config: Config, postgres_url: str
) -> None:
    engine = create_engine(postgres_url)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    user, story, character, fact = (uuid4() for _ in range(4))
    arcs = [uuid4() for _ in range(3)]
    chapters = [uuid4() for _ in range(2)]
    events = [uuid4() for _ in range(3)]
    try:
        command.downgrade(alembic_config, "0001_initial")
        inspector = inspect(engine)
        assert {"scenes", "state_transitions", "memories", "locations"}.isdisjoint(
            inspector.get_table_names()
        )
        assert "state_version" not in {c["name"] for c in inspector.get_columns("stories")}

        with engine.begin() as conn:
            conn.execute(text("INSERT INTO users (id, email, display_name) VALUES (:i, :e, 'x')"),
                         {"i": user, "e": f"{user}@example.com"})
            conn.execute(text("INSERT INTO stories (id, user_id, title, premise) "
                              "VALUES (:i, :u, 't', 'p')"), {"i": story, "u": user})
            conn.execute(text("INSERT INTO characters (id, story_id, name) VALUES (:i, :s, 'c')"),
                         {"i": character, "s": story})
            conn.execute(text("INSERT INTO story_facts (id, story_id, subject, predicate, object, "
                              "valid_from, source) VALUES (:i, :s, 'a', 'b', 'c', now(), 'x')"),
                         {"i": fact, "s": story})
            # Duas posições duplicadas (1, 1) e uma distinta (2): a migration deve renumerar 1..3.
            for index, (arc, position) in enumerate(zip(arcs, (1, 1, 2), strict=True)):
                conn.execute(
                    text("INSERT INTO story_arcs (id, story_id, title, position, status, "
                         "created_at) VALUES (:i, :s, 'a', :p, 'x', :c)"),
                    {"i": arc, "s": story, "p": position, "c": base + timedelta(minutes=index)},
                )
            for index, chapter in enumerate(chapters):
                conn.execute(
                    text("INSERT INTO chapters (id, story_id, arc_id, title, position, status, "
                         "created_at) VALUES (:i, :s, :a, 'c', 7, 'draft', :c)"),
                    {"i": chapter, "s": story, "a": arcs[0], "c": base + timedelta(minutes=index)},
                )
            # Eventos inseridos fora de ordem cronológica.
            for event, offset in zip(events, (30, 10, 20), strict=True):
                conn.execute(
                    text("INSERT INTO story_events (id, story_id, event_type, aggregate_type, "
                         "aggregate_id, payload, occurred_at) "
                         "VALUES (:i, :s, 'e', 'character', :c, '{}'::jsonb, :o)"),
                    {"i": event, "s": story, "c": character, "o": base + timedelta(minutes=offset)},
                )
            conn.execute(
                text("INSERT INTO character_knowledge (id, story_id, character_id, fact_id, "
                     "known_at, confidence, visibility, source_event_id) "
                     "VALUES (gen_random_uuid(), :s, :c, :f, now(), 0.5, 'known', :e)"),
                {"s": story, "c": character, "f": fact, "e": events[0]},
            )

        command.upgrade(alembic_config, "head")

        with engine.connect() as conn:
            arc_positions: dict[Any, Any] = dict(conn.execute(
                text("SELECT id, position FROM story_arcs WHERE story_id = :s"), {"s": story}
            ).all())
            chapter_positions = [r[0] for r in conn.execute(
                text("SELECT position FROM chapters WHERE story_id = :s ORDER BY position"),
                {"s": story},
            ).all()]
            sequences: dict[Any, Any] = dict(conn.execute(
                text("SELECT id, sequence FROM story_events WHERE story_id = :s"), {"s": story}
            ).all())
            version, revision = conn.execute(
                text("SELECT s.state_version, c.revision FROM stories s, chapters c "
                     "WHERE s.id = :s AND c.id = :c"), {"s": story, "c": chapters[0]}
            ).one()
            knowledge_count: int = conn.execute(
                text("SELECT count(*) FROM character_knowledge WHERE story_id = :s"), {"s": story}
            ).scalar_one()

        assert [arc_positions[a] for a in arcs] == [1, 2, 3]
        assert chapter_positions == [1, 2]
        assert (sequences[events[1]], sequences[events[2]], sequences[events[0]]) == (1, 2, 3)
        assert (version, revision, knowledge_count) == (0, 1, 1)

        with engine.begin() as conn:
            new_sequence: int = conn.execute(
                text("INSERT INTO story_events (id, story_id, event_type, aggregate_type, "
                     "aggregate_id, payload, occurred_at) "
                     "VALUES (gen_random_uuid(), :s, 'e', 'character', :c, '{}'::jsonb, now()) "
                     "RETURNING sequence"), {"s": story, "c": character}
            ).scalar_one()
        assert new_sequence == 4
    finally:
        command.upgrade(alembic_config, "head")
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM stories WHERE id = :s"), {"s": story})
            conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": user})
        engine.dispose()


def test_every_revision_downgrades_one_step_at_a_time(
    alembic_config: Config, postgres_url: str
) -> None:
    engine = create_engine(postgres_url)
    steps = [
        "0008_validation", "0007_state_transitions", "0006_user_edits", "0005_generation",
        "0004_narrative_rules", "0003_world_and_scenes", "0002_integrity_hardening",
        "0001_initial",
    ]  # fmt: skip
    try:
        for target in steps:
            command.downgrade(alembic_config, target)
            with engine.connect() as conn:
                current: str = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
            assert current == target
    finally:
        command.upgrade(alembic_config, "head")
        engine.dispose()
