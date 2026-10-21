"""Fluxo de transições propostas: proposta, decisão e aplicação atômica com evento e versão."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from mythra.application.state.transitions import StaleTransitionError
from mythra.application.use_cases import MythraUseCases
from mythra.core.exceptions import ConflictError
from mythra.domain.exceptions import DomainRuleViolation
from mythra.infrastructure.db.models import (
    CharacterKnowledge,
    CharacterRelationship,
    StateTransition,
    StoryEvent,
    StoryFact,
)
from mythra.infrastructure.db.repositories.events import StoryEventRepository

from .conftest import World

MakeWorld = Callable[[], World]
EMOTION = {"emotional_state": {"before": "calma", "after": "medo"}}


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


def _approved(use_cases: MythraUseCases, w: World, **overrides: Any) -> StateTransition:
    transition = use_cases.propose_transition(w.story.id, **_proposal(w, **overrides))
    decided: StateTransition = use_cases.decide_transition(
        w.story.id, transition.id, approve=True, decided_by_user_id=w.user.id
    )
    return decided


def _events(session: Session, w: World, event_type: str) -> list[StoryEvent]:
    query = select(StoryEvent).where(
        StoryEvent.story_id == w.story.id, StoryEvent.event_type == event_type
    )
    return list(session.scalars(query))


def _state(session: Session, w: World) -> tuple[str | None, int]:
    session.refresh(w.character)
    session.refresh(w.story)
    return w.character.emotional_state, w.story.state_version


def test_proposal_persists_without_touching_canonical_state(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()

    transition = use_cases.propose_transition(w.story.id, **_proposal(w))

    assert transition.status == "proposed"
    assert transition.applied_story_event_id is None
    assert _state(db_session, w) == ("calma", 0)
    assert _events(db_session, w, "character_state_updated") == []


def test_approved_transition_is_applied_with_one_event_and_a_new_state_version(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    transition = _approved(use_cases, w)
    assert transition.status == "approved" and transition.decided_at is not None

    (applied,) = use_cases.apply_transitions(w.story.id, [transition.id], expected_state_version=0)

    (event,) = _events(db_session, w, "character_state_updated")
    assert event.payload == {"changes": EMOTION}
    assert event.aggregate_id == w.character.id
    assert applied.status == "applied"
    assert applied.applied_story_event_id == event.id
    assert applied.applied_at is not None
    assert _state(db_session, w) == ("medo", 1)


@pytest.mark.parametrize("approve", [None, False])
def test_only_approved_transitions_can_be_applied(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld, approve: bool | None
) -> None:
    w = make_world()
    transition = use_cases.propose_transition(w.story.id, **_proposal(w))
    if approve is False:
        use_cases.decide_transition(
            w.story.id, transition.id, approve=False, decided_by_user_id=w.user.id
        )

    with pytest.raises(ConflictError):
        use_cases.apply_transitions(w.story.id, [transition.id])

    assert _state(db_session, w) == ("calma", 0)
    assert _events(db_session, w, "character_state_updated") == []


def test_a_transition_can_be_decided_only_once(
    use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    transition = _approved(use_cases, w)

    with pytest.raises(ConflictError):
        use_cases.decide_transition(
            w.story.id, transition.id, approve=False, decided_by_user_id=w.user.id
        )


def test_an_applied_transition_cannot_be_applied_again(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    transition = _approved(use_cases, w)
    use_cases.apply_transitions(w.story.id, [transition.id])

    with pytest.raises(ConflictError):
        use_cases.apply_transitions(w.story.id, [transition.id])

    assert len(_events(db_session, w, "character_state_updated")) == 1
    assert _state(db_session, w) == ("medo", 1)


def test_stale_field_value_blocks_application_and_marks_the_proposal_stale(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    transition = _approved(use_cases, w)
    use_cases.update_character(w.story.id, w.character.id, {"emotional_state": "raiva"})

    with pytest.raises(StaleTransitionError):
        use_cases.apply_transitions(w.story.id, [transition.id])

    db_session.refresh(transition)
    assert transition.status == "stale"
    assert _state(db_session, w) == ("raiva", 1)
    assert len(_events(db_session, w, "character_state_updated")) == 1


def test_expected_state_version_detects_changes_made_after_validation(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    transition = _approved(use_cases, w)
    use_cases.update_character(w.story.id, w.character.id, {"age": 30})

    with pytest.raises(StaleTransitionError):
        use_cases.apply_transitions(w.story.id, [transition.id], expected_state_version=0)

    db_session.refresh(transition)
    assert transition.status == "stale"
    assert _state(db_session, w) == ("calma", 1)


def test_batch_application_is_all_or_nothing(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    relationship = CharacterRelationship(
        story_id=w.story.id, source_character_id=w.character.id,
        target_character_id=w.other_character.id, relationship_type="aliados", trust=0.5,
        status="ativa",
    )  # fmt: skip
    db_session.add(relationship)
    db_session.flush()
    valid = _approved(use_cases, w)
    invalid = _approved(
        use_cases,
        w,
        event_type="relationship_updated",
        aggregate_type="relationship",
        aggregate_id=relationship.id,
        changes={"changes": {"trust": {"before": 0.5, "after": 2.0}}},
    )

    with pytest.raises(DomainRuleViolation):
        use_cases.apply_transitions(w.story.id, [valid.id, invalid.id])

    db_session.refresh(valid)
    db_session.refresh(relationship)
    assert valid.status == "approved" and valid.applied_story_event_id is None
    assert relationship.trust == 0.5
    assert _state(db_session, w) == ("calma", 0)
    assert _events(db_session, w, "character_state_updated") == []


def test_event_insertion_failure_rolls_back_the_applied_state(
    db_session: Session,
    use_cases: MythraUseCases,
    make_world: MakeWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = make_world()
    transition = _approved(use_cases, w)

    def failing_append(*_: object, **__: object) -> None:
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr(StoryEventRepository, "append", failing_append)
    with pytest.raises(RuntimeError):
        use_cases.apply_transitions(w.story.id, [transition.id])
    monkeypatch.undo()

    db_session.refresh(transition)
    assert transition.status == "approved" and transition.applied_story_event_id is None
    assert _state(db_session, w) == ("calma", 0)


def test_fact_creation_transition_creates_the_fact_and_its_event(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    valid_from = datetime(2026, 3, 1, tzinfo=UTC)
    changes = {
        "changes": {
            "subject": {"before": None, "after": "Minos"},
            "predicate": {"before": None, "after": "reina_em"},
            "object": {"before": None, "after": "Creta"},
            "valid_from": {"before": None, "after": valid_from.isoformat()},
            "source": {"before": None, "after": "crônica"},
        }
    }
    transition = _approved(
        use_cases, w,
        event_type="canonical_fact_created", aggregate_type="story_fact", aggregate_id=None,
        operation="create", changes=changes,
    )  # fmt: skip
    assert db_session.scalars(select(StoryFact).where(StoryFact.subject == "Minos")).all() == []

    (applied,) = use_cases.apply_transitions(w.story.id, [transition.id])

    fact = db_session.scalars(select(StoryFact).where(StoryFact.subject == "Minos")).one()
    (event,) = _events(db_session, w, "canonical_fact_created")
    assert fact.valid_from == valid_from
    assert applied.aggregate_id == fact.id and event.aggregate_id == fact.id
    assert applied.applied_story_event_id == event.id
    assert _state(db_session, w)[1] == 1


def test_knowledge_transition_converts_timestamps_and_updates_confidence(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()
    known_at = datetime(2026, 1, 1, tzinfo=UTC)
    knowledge = CharacterKnowledge(
        story_id=w.story.id, character_id=w.character.id, fact_id=w.fact.id, known_at=known_at,
        confidence=0.8, visibility="known", source_event_id=w.event.id,
    )  # fmt: skip
    db_session.add(knowledge)
    db_session.flush()
    new_time = datetime(2026, 2, 1, tzinfo=UTC)
    transition = _approved(
        use_cases, w,
        event_type="character_knowledge_updated", aggregate_type="character_knowledge",
        aggregate_id=knowledge.id,
        changes={"changes": {
            "confidence": {"before": 0.8, "after": 0.4},
            "known_at": {"before": known_at.isoformat(), "after": new_time.isoformat()},
        }},
    )  # fmt: skip

    use_cases.apply_transitions(w.story.id, [transition.id])

    db_session.refresh(knowledge)
    assert (knowledge.confidence, knowledge.known_at) == (0.4, new_time)


@pytest.mark.parametrize(
    "overrides",
    [
        {"generation_run_id": None},
        {"user_edit_id": uuid4()},
        {"event_type": "chapter_updated"},
        {"aggregate_id": None},
        {"operation": "delete"},
        {"changes": {"changes": {}}},
        {"changes": {"changes": {"emotional_state": {"after": "medo"}}}},
        {"operation": "create", "aggregate_type": "character", "aggregate_id": None},
    ],
)
def test_invalid_proposals_are_rejected_before_persisting(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld, overrides: dict[str, Any]
) -> None:
    w = make_world()

    with pytest.raises(DomainRuleViolation):
        use_cases.propose_transition(w.story.id, **_proposal(w, **overrides))

    assert db_session.scalars(select(StateTransition)).all() == []


def test_direct_updates_bump_state_version_and_chapter_revision_only_when_effective(
    db_session: Session, use_cases: MythraUseCases, make_world: MakeWorld
) -> None:
    w = make_world()

    use_cases.update_chapter(w.story.id, w.chapter.id, {"title": w.chapter.title})
    db_session.refresh(w.story)
    db_session.refresh(w.chapter)
    assert (w.story.state_version, w.chapter.revision) == (0, 1)

    use_cases.update_chapter(w.story.id, w.chapter.id, {"title": "Novo título"})
    db_session.refresh(w.story)
    db_session.refresh(w.chapter)
    assert (w.story.state_version, w.chapter.revision) == (1, 2)
