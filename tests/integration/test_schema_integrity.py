"""Integridade do esquema PostgreSQL: constraints, isolamento por história e catálogo."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mythra.infrastructure.db.models import (
    Chapter,
    CharacterKnowledge,
    Faction,
    GenerationEvent,
    GenerationRun,
    Location,
    Memory,
    NarrativeRule,
    Scene,
    StateTransition,
    Story,
    StoryArc,
    StoryEvent,
    UserEdit,
    ValidationResult,
    ValidationRun,
)

from .conftest import World

MakeWorld = Callable[[], World]
NOW = datetime.now(UTC)


def _rejected(session: Session, *objects: Any) -> None:
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add_all(objects)
        session.flush()


def _edit(w: World, **overrides: Any) -> UserEdit:
    values: dict[str, Any] = {
        "story_id": w.story.id,
        "user_id": w.user.id,
        "chapter_id": w.chapter.id,
        "base_revision": 1,
        "resulting_revision": 2,
        "content_before": "a",
        "content_after": "b",
    } | overrides
    return UserEdit(**values)


def _transition(w: World, **overrides: Any) -> StateTransition:
    values: dict[str, Any] = {
        "story_id": w.story.id,
        "generation_run_id": w.run.id,
        "event_type": "character_state_updated",
        "aggregate_type": "character",
        "aggregate_id": w.character.id,
        "operation": "update",
        "changes": {"changes": {"emotional_state": {"before": "calma", "after": "medo"}}},
        "base_state_version": 0,
    } | overrides
    return StateTransition(**values)


def _validation_run(w: World, **overrides: Any) -> ValidationRun:
    values: dict[str, Any] = {
        "story_id": w.story.id,
        "generation_run_id": w.run.id,
        "validator": "consistency_engine",
        "base_state_version": 0,
    } | overrides
    return ValidationRun(**values)


def test_all_documented_tables_and_columns_exist(db_session: Session) -> None:
    inspector = inspect(db_session.get_bind())
    tables = set(inspector.get_table_names())
    assert {
        "locations", "factions", "scenes", "narrative_rules", "memories",
        "generation_runs", "generation_events", "validation_runs", "validation_results",
        "user_edits", "state_transitions", "story_facts",
    } <= tables  # fmt: skip
    expected_columns = {
        "stories": {"state_version"},
        "chapters": {"revision", "generation_run_id"},
        "story_events": {"sequence"},
        "scenes": {"revision", "generation_run_id", "location_id", "timeline_event_id"},
        "state_transitions": {"changes", "base_state_version", "applied_story_event_id"},
        "generation_runs": {"base_state_version", "parameters", "context_manifest", "usage"},
    }
    for table, columns in expected_columns.items():
        assert columns <= {c["name"] for c in inspector.get_columns(table)}, table


def test_catalog_has_deferrable_unique_partial_indexes_identity_and_fk_actions(
    db_session: Session,
) -> None:
    deferrable: dict[Any, Any] = dict(
        db_session.execute(
            text(
                "SELECT conname, condeferrable AND condeferred FROM pg_constraint "
                "WHERE conname IN ('uq_story_arcs_story_id_position', "
                "'uq_chapters_arc_id_position', 'uq_scenes_chapter_id_position')"
            )
        ).all()
    )
    assert deferrable == {
        "uq_story_arcs_story_id_position": True,
        "uq_chapters_arc_id_position": True,
        "uq_scenes_chapter_id_position": True,
    }

    partial: dict[str, str] = {
        str(name): str(definition)
        for name, definition in db_session.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes WHERE indexname IN ("
                "'ix_plot_threads_open_story_id', 'ix_state_transitions_proposed', "
                "'uq_state_transitions_applied_story_event_id')"
            )
        ).all()
    }
    assert set(partial) == {
        "ix_plot_threads_open_story_id",
        "ix_state_transitions_proposed",
        "uq_state_transitions_applied_story_event_id",
    }
    assert all(" WHERE " in definition for definition in partial.values())

    identity = db_session.execute(
        text(
            "SELECT is_identity, identity_generation FROM information_schema.columns "
            "WHERE table_name = 'story_events' AND column_name = 'sequence'"
        )
    ).one()
    assert tuple(identity) == ("YES", "BY DEFAULT")

    delete_action: str = db_session.execute(
        text(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conname = 'fk_knowledge_event_same_story'"
        )
    ).scalar_one()
    assert delete_action == "a"  # NO ACTION


def test_story_events_receive_increasing_sequence(
    db_session: Session, make_world: MakeWorld
) -> None:
    w = make_world()
    later = StoryEvent(
        story_id=w.story.id, event_type="x", aggregate_type="character",
        aggregate_id=uuid4(), payload={}, occurred_at=NOW,
    )  # fmt: skip
    db_session.add(later)
    db_session.flush()
    assert later.sequence > w.event.sequence >= 1


CROSS_STORY_CASES: dict[str, Callable[[World, World], list[Any]]] = {
    "scene_chapter": lambda w, o: [
        Scene(story_id=w.story.id, chapter_id=o.chapter.id, position=9, status="draft")
    ],
    "scene_location": lambda w, o: [
        Scene(story_id=w.story.id, chapter_id=w.chapter.id, position=9, status="d",
              location_id=o.location.id)
    ],
    "scene_timeline_event": lambda w, o: [
        Scene(story_id=w.story.id, chapter_id=w.chapter.id, position=9, status="d",
              timeline_event_id=o.timeline_event.id)
    ],
    "scene_generation_run": lambda w, o: [
        Scene(story_id=w.story.id, chapter_id=w.chapter.id, position=9, status="d",
              generation_run_id=o.run.id)
    ],
    "chapter_arc": lambda w, o: [
        Chapter(story_id=w.story.id, arc_id=o.arc.id, title="x", position=9, status="d")
    ],
    "chapter_generation_run": lambda w, o: [
        Chapter(story_id=w.story.id, arc_id=w.arc.id, title="x", position=9, status="d",
                generation_run_id=o.run.id)
    ],
    "location_parent": lambda w, o: [
        Location(story_id=w.story.id, name="x", parent_location_id=o.location.id)
    ],
    "memory_character": lambda w, o: [
        Memory(story_id=w.story.id, character_id=o.character.id, memory_type="summary", content="x")
    ],
    "memory_source_event": lambda w, o: [
        Memory(story_id=w.story.id, source_event_id=o.event.id, memory_type="summary", content="x")
    ],
    "memory_generation_run": lambda w, o: [
        Memory(story_id=w.story.id, generation_run_id=o.run.id, memory_type="summary", content="x")
    ],
    "user_edit_chapter": lambda w, o: [_edit(w, chapter_id=o.chapter.id)],
    "user_edit_scene": lambda w, o: [_edit(w, chapter_id=None, scene_id=o.scene.id)],
    "validation_run_generation_run": lambda w, o: [_validation_run(w, generation_run_id=o.run.id)],
    "transition_generation_run": lambda w, o: [_transition(w, generation_run_id=o.run.id)],
    "generation_event_run": lambda w, o: [
        GenerationEvent(story_id=w.story.id, generation_run_id=o.run.id, sequence=1,
                        event_type="x", occurred_at=NOW)
    ],
}  # fmt: skip


@pytest.mark.parametrize("case", sorted(CROSS_STORY_CASES))
def test_references_cannot_cross_story_boundaries(
    db_session: Session, make_world: MakeWorld, case: str
) -> None:
    w, other = make_world(), make_world()
    _rejected(db_session, *CROSS_STORY_CASES[case](w, other))


def test_cross_story_references_to_transitions_rules_and_events_are_rejected(
    db_session: Session, make_world: MakeWorld
) -> None:
    w, other = make_world(), make_world()
    run = _validation_run(w)
    foreign_rule = NarrativeRule(
        story_id=other.story.id, rule_type="world", title="r", description="d", severity="error"
    )
    foreign_transition = _transition(other)
    db_session.add_all([run, foreign_rule, foreign_transition])
    db_session.flush()

    for column, value in {
        "narrative_rule_id": foreign_rule.id,
        "state_transition_id": foreign_transition.id,
        "scene_id": other.scene.id,
    }.items():
        _rejected(
            db_session,
            ValidationResult(
                story_id=w.story.id, validation_run_id=run.id, severity="error", code="c",
                message="m", **{column: value},
            ),  # fmt: skip
        )

    transition = _transition(
        w, status="applied", applied_at=NOW, decided_at=NOW, applied_story_event_id=other.event.id
    )
    _rejected(db_session, transition)


INVALID_VALUES: dict[str, Callable[[World], list[Any]]] = {
    "scene_position_zero": lambda w: [
        Scene(story_id=w.story.id, chapter_id=w.chapter.id, position=0, status="d")
    ],
    "scene_revision_zero": lambda w: [
        Scene(story_id=w.story.id, chapter_id=w.chapter.id, position=5, status="d", revision=0)
    ],
    "chapter_revision_zero": lambda w: [
        Chapter(story_id=w.story.id, arc_id=w.arc.id, title="x", position=5, status="d", revision=0)
    ],
    "location_is_own_parent": lambda w: [
        _self_parent_location(w)
    ],
    "faction_duplicate_name_case_insensitive": lambda w: [
        Faction(story_id=w.story.id, name="Ordem"),
        Faction(story_id=w.story.id, name="ORDEM"),
    ],
    "rule_severity": lambda w: [
        NarrativeRule(story_id=w.story.id, rule_type="w", title="t", description="d",
                      severity="fatal")
    ],
    "memory_confidence": lambda w: [
        Memory(story_id=w.story.id, memory_type="s", content="x", confidence=1.5)
    ],
    "memory_status": lambda w: [
        Memory(story_id=w.story.id, memory_type="s", content="x", status="canonical")
    ],
    "run_status": lambda w: [
        GenerationRun(story_id=w.story.id, run_type="c", status="bogus", base_state_version=0)
    ],
    "run_finished_before_started": lambda w: [
        GenerationRun(story_id=w.story.id, run_type="c", base_state_version=0,
                      started_at=NOW, finished_at=NOW - timedelta(seconds=1))
    ],
    "generation_event_sequence_zero": lambda w: [
        GenerationEvent(story_id=w.story.id, generation_run_id=w.run.id, sequence=0,
                        event_type="x", occurred_at=NOW)
    ],
    "generation_event_duplicate_sequence": lambda w: [
        GenerationEvent(story_id=w.story.id, generation_run_id=w.run.id, sequence=1,
                        event_type="x", occurred_at=NOW),
        GenerationEvent(story_id=w.story.id, generation_run_id=w.run.id, sequence=1,
                        event_type="y", occurred_at=NOW),
    ],
    "edit_two_targets": lambda w: [_edit(w, scene_id=w.scene.id)],
    "edit_no_target": lambda w: [_edit(w, chapter_id=None)],
    "edit_revision_not_increasing": lambda w: [_edit(w, resulting_revision=1)],
    "validation_run_no_subject": lambda w: [_validation_run(w, generation_run_id=None)],
    "validation_run_status": lambda w: [_validation_run(w, status="done")],
    "transition_no_origin": lambda w: [_transition(w, generation_run_id=None)],
    "transition_operation": lambda w: [_transition(w, operation="delete")],
    "transition_update_without_aggregate": lambda w: [_transition(w, aggregate_id=None)],
    "transition_status": lambda w: [_transition(w, status="done")],
    "transition_applied_without_event": lambda w: [
        _transition(w, status="applied", applied_at=NOW, decided_at=NOW)
    ],
    "transition_event_while_not_applied": lambda w: [
        _transition(w, applied_story_event_id=w.event.id)
    ],
    "transition_approved_without_decision_time": lambda w: [_transition(w, status="approved")],
}  # fmt: skip


def _self_parent_location(w: World) -> Location:
    identifier = uuid4()
    return Location(id=identifier, story_id=w.story.id, name="loop", parent_location_id=identifier)


@pytest.mark.parametrize("case", sorted(INVALID_VALUES))
def test_check_and_unique_constraints_reject_invalid_rows(
    db_session: Session, make_world: MakeWorld, case: str
) -> None:
    _rejected(db_session, *INVALID_VALUES[case](make_world()))


def test_validation_result_severity_is_checked(db_session: Session, make_world: MakeWorld) -> None:
    w = make_world()
    run = _validation_run(w)
    db_session.add(run)
    db_session.flush()
    _rejected(
        db_session,
        ValidationResult(
            story_id=w.story.id, validation_run_id=run.id, severity="fatal", code="c", message="m"
        ),
    )


def test_one_event_can_be_applied_by_at_most_one_transition(
    db_session: Session, make_world: MakeWorld
) -> None:
    w = make_world()
    applied: dict[str, Any] = {
        "status": "applied", "applied_at": NOW, "decided_at": NOW,
        "applied_story_event_id": w.event.id,
    }  # fmt: skip
    db_session.add(_transition(w, **applied))
    db_session.flush()
    _rejected(db_session, _transition(w, **applied))


def test_valid_applied_transition_and_validation_graph_are_accepted(
    db_session: Session, make_world: MakeWorld
) -> None:
    w = make_world()
    transition = _transition(
        w, status="applied", applied_at=NOW, decided_at=NOW, applied_story_event_id=w.event.id
    )
    run = _validation_run(w, status="failed")
    db_session.add_all([transition, run])
    db_session.flush()
    rule = NarrativeRule(
        story_id=w.story.id, rule_type="world", title="r", description="d", severity="error",
        definition={"kind": "no_resurrection"},
    )  # fmt: skip
    db_session.add(rule)
    db_session.flush()
    db_session.add(
        ValidationResult(
            story_id=w.story.id, validation_run_id=run.id, narrative_rule_id=rule.id,
            state_transition_id=transition.id, scene_id=w.scene.id, severity="error",
            code="rule_violation", message="m", details={"evidence": []},
        )  # fmt: skip
    )
    db_session.flush()


def test_duplicate_positions_are_rejected_when_constraints_are_checked(
    db_session: Session, make_world: MakeWorld
) -> None:
    w = make_world()
    db_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    _rejected(db_session, StoryArc(story_id=w.story.id, title="x", position=1, status="a"))
    _rejected(
        db_session,
        Chapter(story_id=w.story.id, arc_id=w.arc.id, title="x", position=1, status="d"),
    )
    _rejected(
        db_session, Scene(story_id=w.story.id, chapter_id=w.chapter.id, position=1, status="d")
    )


def test_positions_can_be_swapped_inside_one_transaction(
    db_session: Session, make_world: MakeWorld
) -> None:
    w = make_world()
    second = StoryArc(story_id=w.story.id, title="Segundo", position=2, status="active")
    db_session.add(second)
    db_session.flush()

    w.arc.position, second.position = 2, 1
    db_session.flush()
    db_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))

    positions = db_session.scalars(
        select(StoryArc.position).where(StoryArc.story_id == w.story.id).order_by(StoryArc.title)
    ).all()
    assert positions == [2, 1]


def test_generating_a_draft_does_not_change_canonical_state(
    db_session: Session, make_world: MakeWorld
) -> None:
    w = make_world()
    latest_event = select(StoryEvent.sequence).order_by(StoryEvent.sequence.desc())
    events_before = db_session.scalar(latest_event)

    run = GenerationRun(
        story_id=w.story.id, run_type="chapter", status="succeeded", base_state_version=0,
        parameters={"temperature": 0.7}, context_manifest={"facts": [str(w.fact.id)]},
    )  # fmt: skip
    db_session.add(run)
    db_session.flush()
    draft = Chapter(
        story_id=w.story.id, arc_id=w.arc.id, title="Rascunho", position=2, status="draft",
        generation_run_id=run.id,
    )  # fmt: skip
    db_session.add_all(
        [
            draft,
            GenerationEvent(
                story_id=w.story.id, generation_run_id=run.id, sequence=1,
                event_type="output_received", payload={"tokens": 10}, occurred_at=NOW,
            ),  # fmt: skip
            Memory(story_id=w.story.id, generation_run_id=run.id, memory_type="interpretation",
                   content="Ana teme Beto."),
            _transition(w, generation_run_id=run.id),
        ]
    )
    db_session.flush()
    db_session.refresh(w.character)
    db_session.refresh(w.story)

    assert w.character.emotional_state == "calma"
    assert w.story.state_version == 0
    assert db_session.scalar(latest_event) == events_before
    assert db_session.scalars(select(CharacterKnowledge)).all() == []


def test_deleting_a_story_cascades_through_every_dependent_table(
    db_session: Session, make_world: MakeWorld
) -> None:
    w, other = make_world(), make_world()
    knowledge = CharacterKnowledge(
        story_id=w.story.id, character_id=w.character.id, fact_id=w.fact.id, known_at=NOW,
        confidence=0.5, visibility="known", source_event_id=w.event.id,
    )  # fmt: skip
    run = _validation_run(w)
    db_session.add_all([knowledge, run, _edit(w), _transition(w)])
    db_session.add_all(
        [
            Memory(story_id=w.story.id, character_id=w.character.id, memory_type="s", content="x"),
            NarrativeRule(story_id=w.story.id, rule_type="w", title="t", description="d",
                          severity="info"),
            Faction(story_id=w.story.id, name="Ordem"),
            GenerationEvent(story_id=w.story.id, generation_run_id=w.run.id, sequence=1,
                            event_type="x", occurred_at=NOW),
        ]
    )  # fmt: skip
    db_session.flush()
    db_session.add(
        ValidationResult(
            story_id=w.story.id, validation_run_id=run.id, severity="info", code="c", message="m"
        )
    )
    db_session.flush()

    db_session.execute(text("DELETE FROM stories WHERE id = :id"), {"id": w.story.id})

    story_tables = [
        "characters", "story_facts", "story_events", "character_knowledge", "story_arcs",
        "chapters", "scenes", "locations", "factions", "timeline_events", "plot_threads",
        "narrative_rules", "memories", "generation_runs", "generation_events",
        "validation_runs", "validation_results", "user_edits", "state_transitions",
    ]  # fmt: skip
    for table in story_tables:
        remaining: int = db_session.execute(
            text(f"SELECT count(*) FROM {table} WHERE story_id = :id"),  # noqa: S608
            {"id": w.story.id},
        ).scalar_one()
        assert remaining == 0, table
    both = [w.story.id, other.story.id]
    surviving = set(db_session.scalars(select(Story.id).where(Story.id.in_(both))))
    assert surviving == {other.story.id}


def test_events_referenced_by_knowledge_or_applied_transitions_cannot_be_deleted(
    db_session: Session, make_world: MakeWorld
) -> None:
    w = make_world()
    db_session.add(
        CharacterKnowledge(
            story_id=w.story.id, character_id=w.character.id, fact_id=w.fact.id, known_at=NOW,
            confidence=0.5, visibility="known", source_event_id=w.event.id,
        )  # fmt: skip
    )
    db_session.flush()

    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(text("DELETE FROM story_events WHERE id = :id"), {"id": w.event.id})
