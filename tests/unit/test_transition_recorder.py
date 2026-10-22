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


class FakeVersions:
    def __init__(self, on_refresh: Any = None) -> None:
        self.bumps = 0
        self.locked: list[UUID] = []
        self.refreshed: list[Any] = []
        self.on_refresh = on_refresh

    def lock_story(self, story_id: UUID) -> int | None:
        self.locked.append(story_id)
        return 0

    def refresh(self, record: Any) -> None:
        self.refreshed.append(record)
        if self.on_refresh is not None:
            self.on_refresh(record)

    def bump_state_version(self, story_id: UUID) -> int:
        self.bumps += 1
        return self.bumps


def _recorder(events: FakeEvents, uow: FakeUnitOfWork) -> TransitionRecorder:
    return TransitionRecorder(events, FakeVersions(), uow)


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
        operation="update_relationship",
        persist=_persist,
        validate=validate or (lambda _: None),
    )


def test_effective_update_commits_state_and_one_event_together() -> None:
    uow, events = FakeUnitOfWork(), FakeEvents()
    record = _record()

    _update(_recorder(events, uow), record, {"trust": 0.9, "status": "active"})

    assert uow.calls == ["commit"]
    assert len(events.appended) == 1
    assert events.appended[0]["payload"] == {"changes": {"trust": {"before": 0.5, "after": 0.9}}}
    assert events.appended[0]["event_type"] == "relationship_updated"
    assert events.appended[0]["aggregate_id"] == record.id
    assert events.appended[0]["source"] == "user"
    assert events.appended[0]["operation"] == "update_relationship"


def test_timestamps_are_serialized_as_utc_iso_strings() -> None:
    events = FakeEvents()
    new_value = datetime(2026, 3, 1, 12, tzinfo=UTC)

    _update(_recorder(events, FakeUnitOfWork()), _record(), {"seen_at": new_value})

    assert events.appended[0]["payload"]["changes"]["seen_at"] == {
        "before": "2026-01-01T00:00:00+00:00",
        "after": "2026-03-01T12:00:00+00:00",
    }


def test_noop_update_neither_writes_nor_opens_a_transaction() -> None:
    uow, events = FakeUnitOfWork(), FakeEvents()
    record = _record()

    result = _update(_recorder(events, uow), record, {"trust": 0.5})

    assert result is record
    assert uow.calls == [] and events.appended == []


def test_domain_rejection_happens_before_any_write() -> None:
    uow, events = FakeUnitOfWork(), FakeEvents()
    record = _record()

    def reject(_: dict[str, Any]) -> None:
        raise DomainRuleViolation("rejeitado")

    with pytest.raises(DomainRuleViolation):
        _update(_recorder(events, uow), record, {"trust": 0.9}, reject)

    assert record.trust == 0.5
    assert uow.calls == [] and events.appended == []


def test_event_failure_rolls_back_instead_of_committing() -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(RuntimeError):
        _update(_recorder(FakeEvents(fail=True), uow), _record(), {"trust": 0.9})

    assert uow.calls == ["rollback"]


def test_create_records_null_before_for_each_populated_field() -> None:
    uow, events = FakeUnitOfWork(), FakeEvents()
    record = _record()

    _recorder(events, uow).create(
        story_id=uuid4(),
        values={"trust": 0.2, "status": "new", "valid_to": None},
        event_type="canonical_fact_created",
        aggregate_type="story_fact",
        operation="create_fact",
        persist=lambda: record,
    )

    assert uow.calls == ["commit"]
    assert events.appended[0]["payload"] == {
        "changes": {
            "trust": {"before": None, "after": 0.2},
            "status": {"before": None, "after": "new"},
        }
    }


def test_state_version_is_bumped_once_per_effective_change_and_staging_never_commits() -> None:
    uow, events, versions = FakeUnitOfWork(), FakeEvents(), FakeVersions()
    recorder = TransitionRecorder(events, versions, uow)
    record = _record()
    kwargs: dict[str, Any] = {
        "story_id": uuid4(),
        "record": record,
        "event_type": "relationship_updated",
        "aggregate_type": "relationship",
        "operation": "update_relationship",
        "persist": _persist,
        "validate": lambda _: None,
    }

    assert recorder.stage_update(updates={"trust": 0.5}, **kwargs) is None
    staged = recorder.stage_update(updates={"trust": 0.9}, **kwargs)

    assert staged is not None and staged.record is record
    assert versions.bumps == 1
    assert uow.calls == []


def test_update_locks_the_story_and_rereads_the_record_before_deciding() -> None:
    uow, events, versions = FakeUnitOfWork(), FakeEvents(), FakeVersions()
    record = _record()
    story_id = uuid4()

    TransitionRecorder(events, versions, uow).update(
        story_id=story_id,
        record=record,
        updates={"trust": 0.9},
        event_type="relationship_updated",
        aggregate_type="relationship",
        operation="update_relationship",
        persist=_persist,
        validate=lambda _: None,
    )

    assert versions.locked == [story_id]
    assert versions.refreshed == [record]


def test_change_already_made_by_a_concurrent_writer_produces_no_event() -> None:
    uow, events = FakeUnitOfWork(), FakeEvents()
    versions = FakeVersions(on_refresh=lambda record: setattr(record, "trust", 0.9))
    record = _record()

    result = TransitionRecorder(events, versions, uow).update(
        story_id=uuid4(),
        record=record,
        updates={"trust": 0.9},
        event_type="relationship_updated",
        aggregate_type="relationship",
        operation="update_relationship",
        persist=_persist,
        validate=lambda _: None,
    )

    assert result is record
    assert events.appended == [] and versions.bumps == 0
    assert uow.calls == ["commit"]


def test_before_reflects_the_state_read_under_the_lock() -> None:
    events = FakeEvents()
    versions = FakeVersions(on_refresh=lambda record: setattr(record, "trust", 0.1))

    TransitionRecorder(events, versions, FakeUnitOfWork()).update(
        story_id=uuid4(),
        record=_record(),
        updates={"trust": 0.9},
        event_type="relationship_updated",
        aggregate_type="relationship",
        operation="update_relationship",
        persist=_persist,
        validate=lambda _: None,
    )

    assert events.appended[0]["payload"] == {"changes": {"trust": {"before": 0.1, "after": 0.9}}}


def test_creating_the_story_itself_uses_the_new_record_id_as_owner() -> None:
    events, versions = FakeEvents(), FakeVersions()
    record = _record()

    TransitionRecorder(events, versions, FakeUnitOfWork()).create(
        story_id=None,
        values={"title": "t"},
        event_type="story_created",
        aggregate_type="story",
        operation="create_story",
        persist=lambda: record,
    )

    assert versions.locked == [] and versions.bumps == 1
    assert events.appended[0]["aggregate_id"] == record.id
