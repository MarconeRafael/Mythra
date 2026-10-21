"""Registro atômico de transições de estado canônico como StoryEvents."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from mythra.application.events.ports import StateVersionStore, StoryEventStore
from mythra.application.transactions import UnitOfWork, transaction

CHARACTER_STATE_UPDATED = "character_state_updated"
RELATIONSHIP_UPDATED = "relationship_updated"
CHARACTER_KNOWLEDGE_UPDATED = "character_knowledge_updated"
CANONICAL_FACT_CREATED = "canonical_fact_created"
CANONICAL_FACT_UPDATED = "canonical_fact_updated"
TIMELINE_EVENT_UPDATED = "timeline_event_updated"
PLOT_THREAD_UPDATED = "plot_thread_updated"
STORY_ARC_UPDATED = "story_arc_updated"
CHAPTER_UPDATED = "chapter_updated"


def json_value(value: Any) -> Any:
    """Representação JSON estável usada nos payloads de eventos e propostas."""
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _payload(changes: dict[str, tuple[Any, Any]]) -> dict[str, Any]:
    return {
        "changes": {
            field: {"before": json_value(before), "after": json_value(after)}
            for field, (before, after) in changes.items()
        }
    }


@dataclass(frozen=True)
class UpdateTarget:
    """Registro alvo e regras de uma transição de atualização, resolvidos no escopo da história."""

    record: Any
    event_type: str
    aggregate_type: str
    persist: Callable[[Any, dict[str, Any]], Any]
    validate: Callable[[dict[str, Any]], None]

    def as_kwargs(self) -> dict[str, Any]:
        return {
            "record": self.record,
            "event_type": self.event_type,
            "aggregate_type": self.aggregate_type,
            "persist": self.persist,
            "validate": self.validate,
        }
@dataclass(frozen=True)
class StagedChange:
    """Resultado de uma transição preparada na transação corrente, sem commit."""

    record: Any
    event: Any


class TransitionRecorder:
    """Aplica uma transição e seu StoryEvent dentro da mesma transação."""

    def __init__(
        self, events: StoryEventStore, versions: StateVersionStore, unit_of_work: UnitOfWork
    ) -> None:
        self.events = events
        self.versions = versions
        self.unit_of_work = unit_of_work

    def update(
        self,
        *,
        story_id: UUID,
        record: Any,
        updates: dict[str, Any],
        event_type: str,
        aggregate_type: str,
        persist: Callable[[Any, dict[str, Any]], Any],
        validate: Callable[[dict[str, Any]], None],
    ) -> Any:
        """Persiste só campos realmente alterados; sem mudança efetiva não há escrita nem evento."""
        changes = self._prepare(record, updates, validate)
        if not changes:
            return record
        with transaction(self.unit_of_work):
            staged = self._write(story_id, record, changes, event_type, aggregate_type, persist)
        return staged.record

    def stage_update(
        self,
        *,
        story_id: UUID,
        record: Any,
        updates: dict[str, Any],
        event_type: str,
        aggregate_type: str,
        persist: Callable[[Any, dict[str, Any]], Any],
        validate: Callable[[dict[str, Any]], None],
    ) -> StagedChange | None:
        """Valida, grava a mudança, o evento e incrementa a versão; o commit é do chamador."""
        changes = self._prepare(record, updates, validate)
        if not changes:
            return None
        return self._write(story_id, record, changes, event_type, aggregate_type, persist)

    def _prepare(
        self,
        record: Any,
        updates: dict[str, Any],
        validate: Callable[[dict[str, Any]], None],
    ) -> dict[str, tuple[Any, Any]]:
        changes = self.effective_changes(record, updates)
        if changes:
            validate({field: value for field, (_, value) in changes.items()})
        return changes

    def _write(
        self,
        story_id: UUID,
        record: Any,
        changes: dict[str, tuple[Any, Any]],
        event_type: str,
        aggregate_type: str,
        persist: Callable[[Any, dict[str, Any]], Any],
    ) -> StagedChange:
        after = {field: value for field, (_, value) in changes.items()}
        updated = persist(record, after)
        event = self._append(story_id, event_type, aggregate_type, record.id, _payload(changes))
        self.versions.bump_state_version(story_id)
        return StagedChange(updated, event)

    def create(
        self,
        *,
        story_id: UUID,
        values: dict[str, Any],
        event_type: str,
        aggregate_type: str,
        persist: Callable[[], Any],
    ) -> Any:
        """Cria o registro e o evento com `before` nulo para cada campo preenchido."""
        with transaction(self.unit_of_work):
            staged = self.stage_create(
                story_id=story_id,
                values=values,
                event_type=event_type,
                aggregate_type=aggregate_type,
                persist=persist,
            )
        return staged.record

    def stage_create(
        self,
        *,
        story_id: UUID,
        values: dict[str, Any],
        event_type: str,
        aggregate_type: str,
        persist: Callable[[], Any],
    ) -> StagedChange:
        """Versão sem commit de `create`, para uso dentro de uma transação maior."""
        changes = {field: (None, value) for field, value in values.items() if value is not None}
        record = persist()
        event = self._append(story_id, event_type, aggregate_type, record.id, _payload(changes))
        self.versions.bump_state_version(story_id)
        return StagedChange(record, event)

    @staticmethod
    def effective_changes(record: Any, updates: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
        return {
            field: (getattr(record, field), value)
            for field, value in updates.items()
            if getattr(record, field) != value
        }

    def _append(
        self,
        story_id: UUID,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict[str, Any],
    ) -> Any:
        return self.events.append(
            story_id=story_id,
            values={
                "event_type": event_type,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "payload": payload,
                "occurred_at": datetime.now(UTC),
            },
        )
