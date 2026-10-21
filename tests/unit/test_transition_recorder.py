"""Testes unitários da fronteira transacional e do registro de transições."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from mythra.application.events.transitions import TransitionRecorder
from mythra.domain.exceptions import DomainRuleViolation


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def commit(self) -> None:
        self.calls.append("commit")

    def rollback(self) -> None:
        self.calls.append("rollback")


class FakeEvents:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.appended: list[dict[str, Any]] = []

    def append(self, *, story_id: UUID, values: dict[str, Any]) -> None:
        if self.fail:
            raise RuntimeError("falha ao inserir evento")
        self.appended.append(values)

    def list_for_story(self, story_id: UUID) -> list[Any]:
        return []


@dataclass
class Record:
    id: UUID
    trust: float
    status: str
    seen_at: datetime


def _record() -> Record:
    return Record(uuid4(), 0.5, "active", datetime(2026, 1, 1, tzinfo=UTC))


def _persist(record: Record, changes: dict[str, Any]) -> Record:
    for field, value in changes.items():
        setattr(record, field, value)
    return record


def _update(
    recorder: TransitionRecorder, record: Record, updates: dict[str, Any], validate: Any = None
) -> Any:
    return recorder.update(
        story_id=uuid4(),
        record=record,
        updates=updates,
        event_type="relationship_updated",
        aggregate_type="relationship",
        persist=_persist,
        validate=validate or (lambda _: None),
    )


def test_effective_update_commits_state_and_one_event_together() -> None:
    uow, events = FakeUnitOfWork(), FakeEvents()
    record = _record()

    _update(TransitionRecorder(events, uow), record, {"trust": 0.9, "status": "active"})

    assert uow.calls == ["commit"]
    assert len(events.appended) == 1
    assert events.appended[0]["payload"] == {"changes": {"trust": {"before": 0.5, "after": 0.9}}}
    assert events.appended[0]["event_type"] == "relationship_updated"
    assert events.appended[0]["aggregate_id"] == record.id


def test_timestamps_are_serialized_as_utc_iso_strings() -> None:
    events = FakeEvents()
    new_value = datetime(2026, 3, 1, 12, tzinfo=UTC)

    _update(TransitionRecorder(events, FakeUnitOfWork()), _record(), {"seen_at": new_value})

    assert events.appended[0]["payload"]["changes"]["seen_at"] == {
        "before": "2026-01-01T00:00:00+00:00",
        "after": "2026-03-01T12:00:00+00:00",
    }


def test_noop_update_neither_writes_nor_opens_a_transaction() -> None:
    uow, events = FakeUnitOfWork(), FakeEvents()
    record = _record()

    result = _update(TransitionRecorder(events, uow), record, {"trust": 0.5})

    assert result is record
    assert uow.calls == [] and events.appended == []


def test_domain_rejection_happens_before_any_write() -> None:
    uow, events = FakeUnitOfWork(), FakeEvents()
    record = _record()

    def reject(_: dict[str, Any]) -> None:
        raise DomainRuleViolation("rejeitado")

    with pytest.raises(DomainRuleViolation):
        _update(TransitionRecorder(events, uow), record, {"trust": 0.9}, reject)

    assert record.trust == 0.5
    assert uow.calls == [] and events.appended == []


def test_event_failure_rolls_back_instead_of_committing() -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(RuntimeError):
        _update(TransitionRecorder(FakeEvents(fail=True), uow), _record(), {"trust": 0.9})

    assert uow.calls == ["rollback"]


def test_create_records_null_before_for_each_populated_field() -> None:
    uow, events = FakeUnitOfWork(), FakeEvents()
    record = _record()

    TransitionRecorder(events, uow).create(
        story_id=uuid4(),
        values={"trust": 0.2, "status": "new", "valid_to": None},
        event_type="canonical_fact_created",
        aggregate_type="story_fact",
        persist=lambda: record,
    )

    assert uow.calls == ["commit"]
    assert events.appended[0]["payload"] == {
        "changes": {
            "trust": {"before": None, "after": 0.2},
            "status": {"before": None, "after": "new"},
        }
    }
