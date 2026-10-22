"""Replay estrito de eventos: reconstrução válida e detecção de lacunas e inconsistências."""

from typing import Any
from uuid import UUID, uuid4

import pytest

from mythra.domain.events.reconstruction import (
    HistoricalEvent,
    HistoryReconstructionError,
    relationship_spec,
    replay,
)

STORY = uuid4()
SOURCE, TARGET = uuid4(), uuid4()
SPEC = relationship_spec(STORY)


def _event(sequence: int, event_type: str, changes: dict[str, Any]) -> HistoricalEvent:
    return HistoricalEvent(uuid4(), sequence, event_type, {"changes": changes})


def _created(sequence: int = 1, **overrides: Any) -> HistoricalEvent:
    fields: dict[str, Any] = {
        "source_character_id": str(SOURCE),
        "target_character_id": str(TARGET),
        "relationship_type": "aliados",
        "trust": 0.6,
        "status": "friendly",
    } | overrides
    return _event(
        sequence,
        "relationship_created",
        {k: {"before": None, "after": v} for k, v in fields.items()},
    )


def _updated(sequence: int, **fields: tuple[Any, Any]) -> HistoricalEvent:
    return _event(
        sequence,
        "relationship_updated",
        {name: {"before": before, "after": after} for name, (before, after) in fields.items()},
    )


def test_replay_applies_creation_and_updates_in_order() -> None:
    events = [
        _created(1),
        _updated(4, trust=(0.6, -0.7), status=("friendly", "hostile")),
        _updated(9, trust=(-0.7, -0.2)),
    ]

    result = replay(events, SPEC)

    assert result.state["trust"] == -0.2 and result.state["status"] == "hostile"
    assert (result.last_sequence, result.event_count) == (9, 3)
    assert result.last_event_id == events[-1].event_id


def test_replay_of_a_prefix_returns_the_historical_state() -> None:
    events = [_created(1), _updated(2, trust=(0.6, -0.7), status=("friendly", "hostile"))]

    assert replay(events[:1], SPEC).state["status"] == "friendly"


def test_replay_can_start_from_a_known_initial_state() -> None:
    initial: dict[str, Any] = {
        "source_character_id": SOURCE, "target_character_id": TARGET,
        "relationship_type": "aliados", "trust": 0.6, "status": "friendly",
    }  # fmt: skip

    result = replay([_updated(5, trust=(0.6, 0.1))], SPEC, initial_state=initial)

    assert result.state["trust"] == 0.1


def test_replay_without_events_fails() -> None:
    with pytest.raises(HistoryReconstructionError, match="Nenhum evento"):
        replay([], SPEC)


def test_update_without_creation_or_initial_state_is_a_gap() -> None:
    with pytest.raises(HistoryReconstructionError, match="lacuna"):
        replay([_updated(3, trust=(0.6, 0.1))], SPEC)


def test_missing_intermediate_event_is_detected_by_the_before_chain() -> None:
    events = [_created(1), _updated(3, trust=(-0.7, -0.2))]  # falta a mudança 0.6 -> -0.7

    with pytest.raises(HistoryReconstructionError, match="difere do estado reconstruído"):
        replay(events, SPEC)


def test_duplicate_creation_is_rejected() -> None:
    with pytest.raises(HistoryReconstructionError, match="criação duplicada"):
        replay([_created(1), _created(2)], SPEC)


def test_creation_conflicting_with_initial_state_is_rejected() -> None:
    with pytest.raises(HistoryReconstructionError, match="conflitante"):
        replay([_created(1)], SPEC, initial_state={"trust": 0.0})


def test_creation_with_non_null_before_is_rejected() -> None:
    event = _event(1, "relationship_created", {"trust": {"before": 0.1, "after": 0.2}})

    with pytest.raises(HistoryReconstructionError, match="before"):
        replay([event], SPEC)


def test_creation_missing_required_fields_is_rejected() -> None:
    event = _event(1, "relationship_created", {"trust": {"before": None, "after": 0.2}})

    with pytest.raises(HistoryReconstructionError, match="obrigatórios"):
        replay([event], SPEC)


def test_update_of_a_non_updatable_field_is_rejected() -> None:
    events = [_created(1), _updated(2, relationship_type=("aliados", "rivais"))]

    with pytest.raises(HistoryReconstructionError, match="não atualizáveis"):
        replay(events, SPEC)


@pytest.mark.parametrize("sequences", [(2, 2), (3, 2)])
def test_out_of_order_or_duplicated_sequences_are_rejected(sequences: tuple[int, int]) -> None:
    events = [_created(sequences[0]), _updated(sequences[1], trust=(0.6, 0.1))]

    with pytest.raises(HistoryReconstructionError, match="sequência"):
        replay(events, SPEC)


def test_unexpected_event_type_is_rejected() -> None:
    other = _event(2, "chapter_updated", {"title": {"before": "a", "after": "b"}})

    with pytest.raises(HistoryReconstructionError, match="inesperado"):
        replay([_created(1), other], SPEC)


@pytest.mark.parametrize(
    "payload", [{}, {"changes": {}}, {"changes": {"trust": {"after": 0.1}}}, {"changes": []}]
)
def test_malformed_payloads_are_rejected(payload: dict[str, Any]) -> None:
    bad = HistoricalEvent(uuid4(), 2, "relationship_updated", payload)

    with pytest.raises(HistoryReconstructionError):
        replay([_created(1), bad], SPEC)


def test_domain_invariants_are_checked_after_every_event() -> None:
    events = [_created(1), _updated(2, trust=(0.6, 2.0))]

    with pytest.raises(HistoryReconstructionError, match="trust"):
        replay(events, SPEC)


def test_self_referencing_relationship_is_rejected() -> None:
    loop = _created(1, target_character_id=str(SOURCE))

    with pytest.raises(HistoryReconstructionError, match="consigo mesma"):
        replay([loop], SPEC)


def test_error_message_identifies_the_failing_event() -> None:
    failing = _updated(7, trust=(0.0, 0.1))

    with pytest.raises(HistoryReconstructionError) as error:
        replay([_created(1), failing], SPEC)

    assert str(failing.event_id) in str(error.value) and "sequência 7" in str(error.value)
    assert isinstance(UUID(str(failing.event_id)), UUID)
