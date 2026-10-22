"""Modelo híbrido: estado atual + log imutável de eventos, histórico e reconstrução."""

import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from mythra.application.state.transitions import StaleTransitionError
from mythra.application.use_cases import MythraUseCases
from mythra.core.exceptions import ConflictError, ResourceNotFoundError
from mythra.domain.events.reconstruction import HistoryReconstructionError
from mythra.domain.exceptions import DomainRuleViolation
from mythra.infrastructure.db.models import (
    CharacterRelationship,
    StateTransition,
    Story,
    StoryEvent,
)
from mythra.infrastructure.db.repositories.events import StoryEventRepository

from .conftest import World, build_use_cases

MakeWorld = Callable[[], World]
T0 = datetime(2026, 1, 1, tzinfo=UTC)
FRIENDLY = {"relationship_type": "aliados", "trust": 0.6, "status": "friendly"}
EMOTION = {"emotional_state": {"before": "calma", "after": "medo"}}


def _relationship(uc: MythraUseCases, w: World) -> CharacterRelationship:
    values = {
        "source_character_id": w.character.id,
        "target_character_id": w.other_character.id,
    } | FRIENDLY
    created: CharacterRelationship = uc.create_relationship(w.story.id, values)
    return created


def _types(uc: MythraUseCases, story_id: UUID, **filters: Any) -> list[str]:
    return [e.event_type for e in uc.list_event_history(story_id, **filters)]


def _history(uc: MythraUseCases, w: World, **filters: Any) -> list[Any]:
    """Histórico posterior ao evento de sementes criado pela fábrica de histórias."""
    return uc.list_event_history(w.story.id, after_sequence=w.event.sequence, **filters)


def _character_history(uc: MythraUseCases, w: World, character_id: UUID) -> list[Any]:
    events = uc.list_character_event_history(w.story.id, character_id)
    return [e for e in events if e.id != w.event.id]


def _failing_append(*_: object, **__: object) -> None:
    raise RuntimeError("event store unavailable")


def _manual_event(uc: MythraUseCases, story_id: UUID, **overrides: Any) -> Any:
    values: dict[str, Any] = {
        "event_type": "marco",
        "aggregate_type": "story",
        "aggregate_id": story_id,
        "payload": {},
        "occurred_at": T0,
    } | overrides
    return uc.record_story_event(story_id, values)


# --- 1. mudança válida registrada e criações auditadas ---------------------------------------


def test_every_audited_creation_emits_exactly_one_event_and_a_state_version(
    db_session: Session, use_cases: MythraUseCases
) -> None:
    uc = use_cases
    user = uc.create_user(f"{uuid4()}@example.com", "Autora")
    story = uc.create_story(user.id, "Labirinto", "Uma cidade perdida.")
    sid = story.id
    uc.create_preferences(sid, "mítico")
    ana = uc.create_character(sid, {"name": "Ana", "age": 24})
    beto = uc.create_character(sid, {"name": "Beto"})
    uc.create_relationship(
        sid, {"source_character_id": ana.id, "target_character_id": beto.id} | FRIENDLY
    )
    fact_values = {
        "subject": "Ana", "predicate": "ajudou", "object": "Beto",
        "valid_from": T0, "source": "s",
    }  # fmt: skip
    fact = uc.create_fact(sid, fact_values)
    note = _manual_event(uc, sid, event_type="cena_testemunhada", aggregate_id=ana.id)
    knowledge_values = {
        "story_id": sid, "fact_id": fact.id, "known_at": T0, "confidence": 0.8,
        "visibility": "known", "source_event_id": note.id,
    }  # fmt: skip
    uc.create_knowledge(sid, ana.id, knowledge_values)
    arc = uc.create_arc(sid, {"title": "Exílio", "position": 1, "status": "active"})
    chapter_values = {"arc_id": arc.id, "title": "Estrada", "position": 1, "status": "draft"}
    uc.create_chapter(sid, chapter_values)
    uc.create_timeline_event(sid, {"title": "Partida", "occurred_at": T0})
    uc.create_plot_thread(sid, {"title": "Retorno", "status": "open"})

    events = uc.list_event_history(sid)

    assert [e.event_type for e in events] == [
        "story_created", "story_preferences_created", "character_created", "character_created",
        "relationship_created", "canonical_fact_created", "cena_testemunhada",
        "character_knowledge_created", "story_arc_created", "chapter_created",
        "timeline_event_created", "plot_thread_created",
    ]  # fmt: skip
    assert [e.operation for e in events if e.event_type != "cena_testemunhada"] == [
        "create_story", "create_preferences", "create_character", "create_character",
        "create_relationship", "create_fact", "create_knowledge", "create_arc",
        "create_chapter", "create_timeline_event", "create_plot_thread",
    ]  # fmt: skip
    assert {e.source for e in events} == {"user"}
    sequences = [e.sequence for e in events]
    assert sequences == sorted(set(sequences))
    db_session.refresh(story)
    assert story.state_version == 11  # o evento manual (anotação) não altera estado
    created = events[0]
    assert created.aggregate_type == "story" and created.aggregate_id == sid
    assert created.payload == {
        "changes": {
            "user_id": {"before": None, "after": str(user.id)},
            "title": {"before": None, "after": "Labirinto"},
            "premise": {"before": None, "after": "Uma cidade perdida."},
        }
    }
    knowledge_event = next(e for e in events if e.event_type == "character_knowledge_created")
    assert knowledge_event.payload["changes"]["character_id"]["after"] == str(ana.id)
    assert "story_id" not in knowledge_event.payload["changes"]


def test_relationship_change_updates_state_and_records_before_and_after(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    relationship = _relationship(use_cases, w)

    use_cases.update_relationship(w.story.id, relationship.id, {"trust": -0.7, "status": "hostile"})

    db_session.refresh(relationship)
    assert (relationship.trust, relationship.status) == (-0.7, "hostile")
    (event,) = use_cases.list_event_history(w.story.id, event_type="relationship_updated")
    assert event.payload == {
        "changes": {
            "trust": {"before": 0.6, "after": -0.7},
            "status": {"before": "friendly", "after": "hostile"},
        }
    }
    assert (event.aggregate_type, event.aggregate_id) == ("relationship", relationship.id)
    assert (event.source, event.operation) == ("user", "update_relationship")
    assert event.state_transition_id is None and event.generation_run_id is None


def test_story_update_records_event_and_repeating_it_records_nothing(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    sid = w.story.id

    use_cases.update_story(sid, {"title": "Novo título"})
    use_cases.update_story(sid, {"title": "Novo título"})

    (event,) = use_cases.list_event_history(sid, event_type="story_updated")
    assert event.payload == {"changes": {"title": {"before": "História", "after": "Novo título"}}}
    with pytest.raises(DomainRuleViolation):
        use_cases.update_story(sid, {"title": " "})
    assert len(use_cases.list_event_history(sid, event_type="story_updated")) == 1


# --- 2. rollback quando a inserção do evento falha -------------------------------------------


def test_failed_event_insertion_rolls_back_creations(
    db_session: Session,
    use_cases: MythraUseCases,
    make_world: MakeWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = make_world()
    monkeypatch.setattr(StoryEventRepository, "append", _failing_append)
    values = {
        "source_character_id": w.character.id,
        "target_character_id": w.other_character.id,
    } | FRIENDLY

    with pytest.raises(RuntimeError):
        use_cases.create_relationship(w.story.id, values)
    with pytest.raises(RuntimeError):
        use_cases.create_story(w.user.id, "Perdida", "Premissa")
    monkeypatch.undo()

    assert db_session.scalars(select(CharacterRelationship)).all() == []
    assert db_session.scalars(select(Story.id).where(Story.title == "Perdida")).all() == []
    assert use_cases.list_event_history(w.story.id, event_type="relationship_created") == []


def test_failed_event_insertion_rolls_back_story_updates(
    db_session: Session,
    use_cases: MythraUseCases,
    make_world: MakeWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = make_world()
    monkeypatch.setattr(StoryEventRepository, "append", _failing_append)

    with pytest.raises(RuntimeError):
        use_cases.update_story(w.story.id, {"title": "Fantasma"})
    monkeypatch.undo()

    db_session.refresh(w.story)
    assert (w.story.title, w.story.state_version) == ("História", 0)


# --- 3. ausência de eventos para operações sem efeito ----------------------------------------


def test_retrying_an_update_never_duplicates_the_event(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    relationship = _relationship(use_cases, w)

    for _ in range(3):
        use_cases.update_relationship(w.story.id, relationship.id, {"trust": 0.1})

    assert _types(use_cases, w.story.id, after_sequence=w.event.sequence) == [
        "relationship_created",
        "relationship_updated",
    ]


def test_rejected_update_leaves_no_event(use_cases: MythraUseCases, make_world: MakeWorld) -> None:
    w = make_world()
    relationship = _relationship(use_cases, w)

    with pytest.raises(DomainRuleViolation):
        use_cases.update_relationship(w.story.id, relationship.id, {"trust": 5.0})

    assert _types(use_cases, w.story.id, after_sequence=w.event.sequence) == [
        "relationship_created"
    ]


# --- 4. imutabilidade ------------------------------------------------------------------------


def _rejected(session: Session, statement: str, **params: Any) -> None:
    with pytest.raises(IntegrityError, match="append-only"), session.begin_nested():
        session.execute(text(statement), params)


def test_events_cannot_be_updated_or_deleted_by_sql(
    db_session: Session, make_world: MakeWorld
) -> None:
    w = make_world()
    event_id = w.event.id

    _rejected(db_session, "UPDATE story_events SET payload = '{}'::jsonb WHERE id = :i", i=event_id)
    _rejected(db_session, "UPDATE story_events SET event_type = 'x' WHERE id = :i", i=event_id)
    _rejected(db_session, "UPDATE story_events SET sequence = 9999999 WHERE id = :i", i=event_id)
    _rejected(db_session, "DELETE FROM story_events WHERE id = :i", i=event_id)
    _rejected(db_session, "DELETE FROM story_events WHERE story_id = :s", s=w.story.id)
    _rejected(db_session, "TRUNCATE story_events CASCADE")
    with pytest.raises(DBAPIError), db_session.begin_nested():  # bloqueado também pelas FKs
        db_session.execute(text("TRUNCATE story_events"))

    assert db_session.scalar(select(StoryEvent.id).where(StoryEvent.id == event_id)) == event_id


def test_events_cannot_be_changed_or_removed_through_the_orm(
    db_session: Session, make_world: MakeWorld
) -> None:
    w = make_world()

    with pytest.raises(IntegrityError, match="append-only"), db_session.begin_nested():
        w.event.payload = {"adulterado": True}
        db_session.flush()
    db_session.expire_all()

    with pytest.raises(IntegrityError, match="append-only"), db_session.begin_nested():
        db_session.delete(w.event)
        db_session.flush()
    db_session.expire_all()
    assert db_session.get(StoryEvent, w.event.id) is not None


def test_events_still_disappear_together_with_their_story(
    db_session: Session, make_world: MakeWorld
) -> None:
    w = make_world()

    db_session.execute(text("DELETE FROM stories WHERE id = :s"), {"s": w.story.id})

    remaining = db_session.scalar(
        text("SELECT count(*) FROM story_events WHERE story_id = :s"), {"s": w.story.id}
    )
    assert remaining == 0


def test_event_source_is_restricted(db_session: Session, make_world: MakeWorld) -> None:
    w = make_world()
    bad = StoryEvent(
        story_id=w.story.id, event_type="x", aggregate_type="character", aggregate_id=uuid4(),
        source="robot", operation="x", payload={}, occurred_at=T0,
    )  # fmt: skip

    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(bad)
        db_session.flush()


# --- 5. sequência determinística -------------------------------------------------------------


def test_sequence_follows_insertion_order_even_with_backdated_timestamps(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    sid = w.story.id
    for day, title in ((20, "depois"), (1, "antes")):  # ocorrência anterior, inserida depois
        when = datetime(2026, 1, day, tzinfo=UTC)
        _manual_event(use_cases, sid, event_type=title, occurred_at=when)

    ordered = use_cases.list_event_history(sid)

    assert [e.event_type for e in ordered[-2:]] == ["depois", "antes"]
    sequences = [e.sequence for e in ordered]
    assert sequences == sorted(set(sequences))


def test_history_can_be_paginated_by_sequence(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    relationship = _relationship(use_cases, w)
    for value in (0.1, 0.2, 0.3):
        use_cases.update_relationship(w.story.id, relationship.id, {"trust": value})
    everything = _history(use_cases, w)

    first_page = _history(use_cases, w, limit=2)
    second_page = use_cases.list_event_history(
        w.story.id, after_sequence=first_page[-1].sequence, limit=2
    )
    prefix = use_cases.list_event_history(w.story.id, up_to_sequence=everything[1].sequence)

    assert [e.id for e in first_page + second_page] == [e.id for e in everything]
    assert [e.id for e in prefix] == [w.event.id] + [e.id for e in everything[:2]]


# --- 6. filtragem ----------------------------------------------------------------------------


def test_history_is_filtered_by_story_type_entity_and_source(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w, other = make_world(), make_world()
    relationship = _relationship(use_cases, w)
    other_relationship = _relationship(use_cases, other)
    use_cases.update_relationship(w.story.id, relationship.id, {"trust": 0.2})
    use_cases.update_relationship(other.story.id, other_relationship.id, {"trust": 0.3})
    use_cases.update_character(w.story.id, w.character.id, {"emotional_state": "medo"})

    in_story = _history(use_cases, w)
    assert {e.story_id for e in in_story} == {w.story.id}
    assert _types(use_cases, w.story.id, event_type="relationship_updated") == [
        "relationship_updated"
    ]
    by_entity = use_cases.list_event_history(
        w.story.id, aggregate_type="relationship", aggregate_id=relationship.id
    )
    assert [e.event_type for e in by_entity] == ["relationship_created", "relationship_updated"]
    assert _types(use_cases, w.story.id, aggregate_id=other_relationship.id) == []
    assert len(_history(use_cases, w, source="user")) == len(in_story)
    assert _history(use_cases, w, source="generation") == []


def test_character_history_includes_its_relationships_and_knowledge(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w, other = make_world(), make_world()
    relationship = _relationship(use_cases, w)
    use_cases.update_relationship(w.story.id, relationship.id, {"trust": 0.2})
    use_cases.update_character(w.story.id, w.character.id, {"emotional_state": "medo"})
    use_cases.update_character(w.story.id, w.other_character.id, {"emotional_state": "raiva"})
    knowledge_values = {
        "story_id": w.story.id, "fact_id": w.fact.id, "known_at": T0, "confidence": 0.5,
        "visibility": "known", "source_event_id": w.event.id,
    }  # fmt: skip
    use_cases.create_knowledge(w.story.id, w.character.id, knowledge_values)

    ana = _character_history(use_cases, w, w.character.id)
    beto = _character_history(use_cases, w, w.other_character.id)

    assert [e.event_type for e in ana] == [
        "relationship_created", "relationship_updated", "character_state_updated",
        "character_knowledge_created",
    ]  # fmt: skip
    assert [e.event_type for e in beto] == [
        "relationship_created", "relationship_updated", "character_state_updated",
    ]  # fmt: skip
    with pytest.raises(ResourceNotFoundError):
        use_cases.list_character_event_history(w.story.id, other.character.id)


def test_history_of_an_unknown_story_is_not_found(use_cases: MythraUseCases) -> None:
    with pytest.raises(ResourceNotFoundError):
        use_cases.list_event_history(uuid4())


# --- 7. integridade entre eventos e transições -----------------------------------------------


def _proposal(w: World, **overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "generation_run_id": w.run.id,
        "user_edit_id": None,
        "event_type": "character_state_updated",
        "aggregate_type": "character",
        "aggregate_id": w.character.id,
        "operation": "update",
        "changes": {"changes": EMOTION},
        "base_state_version": 0,
    } | overrides
    return values


def _approved(uc: MythraUseCases, w: World, **overrides: Any) -> Any:
    transition = uc.propose_transition(w.story.id, **_proposal(w, **overrides))
    return uc.decide_transition(
        w.story.id, transition.id, approve=True, decided_by_user_id=w.user.id
    )


def _applied_transition(uc: MythraUseCases, w: World) -> Any:
    transition = _approved(uc, w)
    (applied,) = uc.apply_transitions(w.story.id, [transition.id])
    return applied


def test_applied_transition_is_linked_to_exactly_one_event_with_its_origin(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()

    applied = _applied_transition(use_cases, w)

    events = _history(use_cases, w, aggregate_id=w.character.id)
    (event,) = [e for e in events if e.operation == "apply_transition"]
    assert applied.applied_story_event_id == event.id
    assert (event.source, event.event_type) == ("generation", "character_state_updated")
    assert event.payload == applied.changes
    assert (event.state_transition_id, event.generation_run_id) == (applied.id, w.run.id)
    assert use_cases.get_event_for_transition(w.story.id, applied.id).id == event.id


def test_unapplied_transitions_have_no_event_and_do_not_touch_history(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    transition = use_cases.propose_transition(w.story.id, **_proposal(w))
    use_cases.decide_transition(
        w.story.id, transition.id, approve=False, decided_by_user_id=w.user.id
    )

    with pytest.raises(ResourceNotFoundError):
        use_cases.get_event_for_transition(w.story.id, transition.id)
    assert _history(use_cases, w) == []


def test_database_rejects_an_applied_transition_linked_to_a_mismatching_event(
    db_session: Session, make_world: MakeWorld
) -> None:
    w = make_world()
    mismatching: dict[str, dict[str, Any]] = {
        "other_type": {"event_type": "chapter_updated"},
        "other_aggregate": {"aggregate_id": uuid4()},
        "other_source": {"source": "user"},
    }
    for override in mismatching.values():
        base: dict[str, Any] = {
            "story_id": w.story.id, "event_type": "character_state_updated",
            "aggregate_type": "character", "aggregate_id": w.character.id,
            "source": "generation", "operation": "apply_transition", "payload": {},
            "occurred_at": T0,
        }  # fmt: skip
        event = StoryEvent(**(base | override))
        db_session.add(event)
        db_session.flush()
        transition = StateTransition(
            story_id=w.story.id, generation_run_id=w.run.id,
            event_type="character_state_updated", aggregate_type="character",
            aggregate_id=w.character.id, operation="update", changes={"changes": EMOTION},
            base_state_version=0, status="applied", decided_at=T0, applied_at=T0,
            applied_story_event_id=event.id,
        )  # fmt: skip
        with pytest.raises(IntegrityError, match="não corresponde"), db_session.begin_nested():
            db_session.add(transition)
            db_session.flush()


def test_a_second_application_of_the_same_transition_adds_no_event(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    applied = _applied_transition(use_cases, w)
    before = len(use_cases.list_event_history(w.story.id))

    with pytest.raises(ConflictError, match="aprovadas"):
        use_cases.apply_transitions(w.story.id, [applied.id])

    assert len(use_cases.list_event_history(w.story.id)) == before


# --- 10/11. reconstrução histórica -----------------------------------------------------------


def test_relationship_is_reconstructed_at_any_point_of_its_history(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    sid = w.story.id
    relationship = _relationship(use_cases, w)
    use_cases.update_relationship(sid, relationship.id, {"trust": -0.7, "status": "hostile"})
    use_cases.update_relationship(sid, relationship.id, {"trust": -0.2})
    created, hostile, softened = _history(use_cases, w)

    at_creation = use_cases.reconstruct_relationship(
        sid, relationship.id, up_to_sequence=created.sequence
    )
    at_hostile = use_cases.reconstruct_relationship(
        sid, relationship.id, up_to_sequence=hostile.sequence
    )
    latest = use_cases.reconstruct_relationship(sid, relationship.id, verify_current=True)

    assert (at_creation.trust, at_creation.status) == (0.6, "friendly")
    assert (at_hostile.trust, at_hostile.status) == (-0.7, "hostile")
    assert (latest.trust, latest.status, latest.event_count) == (-0.2, "hostile", 3)
    assert latest.as_of_sequence == softened.sequence and latest.last_event_id == softened.id
    assert latest.source_character_id == w.character.id


def test_reconstruction_includes_changes_applied_through_transitions(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    relationship = _relationship(use_cases, w)
    transition = _approved(
        use_cases, w,
        event_type="relationship_updated", aggregate_type="relationship",
        aggregate_id=relationship.id,
        changes={"changes": {"trust": {"before": 0.6, "after": -0.9}}},
        base_state_version=1,
    )  # fmt: skip
    use_cases.apply_transitions(w.story.id, [transition.id])

    rebuilt = use_cases.reconstruct_relationship(w.story.id, relationship.id, verify_current=True)

    assert rebuilt.trust == -0.9 and rebuilt.event_count == 2


def test_reconstruction_before_the_entity_existed_fails(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    seed = _manual_event(use_cases, w.story.id)
    relationship = _relationship(use_cases, w)

    with pytest.raises(HistoryReconstructionError, match="Nenhum evento"):
        use_cases.reconstruct_relationship(
            w.story.id, relationship.id, up_to_sequence=seed.sequence
        )


def test_manual_events_never_enter_the_reconstruction(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    relationship = _relationship(use_cases, w)
    _manual_event(
        use_cases, w.story.id,
        event_type="relationship_updated", aggregate_type="relationship",
        aggregate_id=relationship.id,
        payload={"changes": {"trust": {"before": 0.6, "after": -1.0}}},
    )  # fmt: skip

    rebuilt = use_cases.reconstruct_relationship(w.story.id, relationship.id, verify_current=True)

    assert (rebuilt.trust, rebuilt.event_count) == (0.6, 1)


def _change_without_event(session: Session, relationship_id: UUID) -> None:
    session.execute(
        text("UPDATE character_relationships SET trust = 0.9 WHERE id = :i"),
        {"i": relationship_id},
    )
    session.expire_all()


def test_change_made_without_an_event_is_detected(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    relationship = _relationship(use_cases, w)
    _change_without_event(db_session, relationship.id)

    with pytest.raises(HistoryReconstructionError, match="mudança sem evento"):
        use_cases.reconstruct_relationship(w.story.id, relationship.id, verify_current=True)


def test_missing_event_in_the_chain_is_detected(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    relationship = _relationship(use_cases, w)
    _change_without_event(db_session, relationship.id)
    use_cases.update_relationship(w.story.id, relationship.id, {"trust": 0.2})  # before=0.9

    with pytest.raises(HistoryReconstructionError, match="difere do estado reconstruído"):
        use_cases.reconstruct_relationship(w.story.id, relationship.id)


def test_legacy_relationship_without_creation_event_needs_a_known_initial_state(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    legacy = CharacterRelationship(
        story_id=w.story.id, source_character_id=w.character.id,
        target_character_id=w.other_character.id, **FRIENDLY,
    )  # fmt: skip
    db_session.add(legacy)
    db_session.flush()
    use_cases.update_relationship(w.story.id, legacy.id, {"trust": 0.3})
    initial = {
        "source_character_id": str(w.character.id),
        "target_character_id": str(w.other_character.id),
    } | FRIENDLY

    with pytest.raises(HistoryReconstructionError, match="lacuna"):
        use_cases.reconstruct_relationship(w.story.id, legacy.id)
    rebuilt = use_cases.reconstruct_relationship(
        w.story.id, legacy.id, initial_state=initial, verify_current=True
    )

    assert rebuilt.trust == 0.3


def test_verify_current_requires_the_full_history(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    relationship = _relationship(use_cases, w)

    with pytest.raises(ValueError, match="verify_current"):
        use_cases.reconstruct_relationship(
            w.story.id, relationship.id, up_to_sequence=1, verify_current=True
        )


# --- 9. concorrência -------------------------------------------------------------------------


def _committed_relationship(engine: Any) -> tuple[UUID, UUID, UUID]:
    with Session(engine) as session:
        uc = build_use_cases(session)
        user = uc.create_user(f"{uuid4()}@example.com", "Autora")
        story = uc.create_story(user.id, "Concorrência", "Premissa")
        ana = uc.create_character(story.id, {"name": "Ana"})
        beto = uc.create_character(story.id, {"name": "Beto"})
        values = {"source_character_id": ana.id, "target_character_id": beto.id} | FRIENDLY
        relationship = uc.create_relationship(story.id, values)
        return user.id, story.id, relationship.id


def _cleanup(engine: Any, user_id: UUID, story_id: UUID) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM stories WHERE id = :s"), {"s": story_id})
        conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})
    engine.dispose()


def test_concurrent_writer_is_serialized_and_before_is_read_under_the_lock(
    postgres_url: str,
) -> None:
    engine = create_engine(postgres_url)
    user_id, story_id, relationship_id = _committed_relationship(engine)
    outcome: dict[str, Any] = {}

    def second_writer() -> None:
        try:
            with Session(engine) as session:
                build_use_cases(session).update_relationship(
                    story_id, relationship_id, {"trust": 0.9}
                )
        except Exception as error:  # pragma: no cover - reportado pela asserção principal
            outcome["error"] = error

    try:
        with engine.connect() as holder:
            lock = "SELECT id FROM stories WHERE id = :s FOR UPDATE"
            holder.execute(text(lock), {"s": story_id})
            holder.execute(
                text("UPDATE character_relationships SET trust = 0.1 WHERE id = :r"),
                {"r": relationship_id},
            )
            worker = threading.Thread(target=second_writer)
            worker.start()
            time.sleep(1.0)
            assert worker.is_alive(), "a escrita deveria aguardar o bloqueio da história"
            holder.commit()
        worker.join(timeout=15)

        assert not worker.is_alive() and "error" not in outcome
        with Session(engine) as session:
            uc = build_use_cases(session)
            (event,) = uc.list_event_history(story_id, event_type="relationship_updated")
            assert event.payload["changes"]["trust"] == {"before": 0.1, "after": 0.9}
    finally:
        _cleanup(engine, user_id, story_id)


def test_parallel_updates_keep_a_consistent_event_chain(postgres_url: str) -> None:
    engine = create_engine(postgres_url)
    user_id, story_id, relationship_id = _committed_relationship(engine)
    errors: list[Exception] = []
    values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, -0.1, -0.2]  # nenhum igual ao 0.6 inicial

    def writer(value: float) -> None:
        try:
            with Session(engine) as session:
                build_use_cases(session).update_relationship(
                    story_id, relationship_id, {"trust": value}
                )
        except Exception as error:  # pragma: no cover
            errors.append(error)

    try:
        threads = [threading.Thread(target=writer, args=(v,)) for v in values]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert errors == []
        with Session(engine) as session:
            uc = build_use_cases(session)
            rebuilt = uc.reconstruct_relationship(story_id, relationship_id, verify_current=True)
            updates = uc.list_event_history(story_id, event_type="relationship_updated")
            version = session.scalar(select(Story.state_version).where(Story.id == story_id))
        assert len(updates) == len(values) and rebuilt.event_count == len(values) + 1
        assert version == 4 + len(values)  # história, 2 personagens, relação e as atualizações
    finally:
        _cleanup(engine, user_id, story_id)


def test_apply_conflicts_with_a_concurrent_direct_change(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    transition = _approved(use_cases, w)
    use_cases.update_character(w.story.id, w.character.id, {"emotional_state": "raiva"})

    with pytest.raises(StaleTransitionError):
        use_cases.apply_transitions(w.story.id, [transition.id])

    events = _history(use_cases, w, aggregate_id=w.character.id)
    assert [e.operation for e in events] == ["update_character"]  # nenhum evento falso
