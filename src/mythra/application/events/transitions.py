"""Registro atômico de transições de estado canônico como StoryEvents."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from mythra.application.events.ports import StoryEventStore
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


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _payload(changes: dict[str, tuple[Any, Any]]) -> dict[str, Any]:
    return {
        "changes": {
            field: {"before": _json_value(before), "after": _json_value(after)}
            for field, (before, after) in changes.items()
        }
    }


class TransitionRecorder:
    """Aplica uma transição e seu StoryEvent dentro da mesma transação."""

    def __init__(self, events: StoryEventStore, unit_of_work: UnitOfWork) -> None:
        self.events = events
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
        changes = {
            field: (getattr(record, field), value)
            for field, value in updates.items()
            if getattr(record, field) != value
        }
        if not changes:
            return record
        after = {field: value for field, (_, value) in changes.items()}
        validate(after)
        with transaction(self.unit_of_work):
            updated = persist(record, after)
            self._append(story_id, event_type, aggregate_type, record.id, _payload(changes))
        return updated

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
        changes = {field: (None, value) for field, value in values.items() if value is not None}
        with transaction(self.unit_of_work):
            record = persist()
            self._append(story_id, event_type, aggregate_type, record.id, _payload(changes))
        return record

    def _append(
        self,
        story_id: UUID,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        self.events.append(
            story_id=story_id,
            values={
                "event_type": event_type,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "payload": payload,
                "occurred_at": datetime.now(UTC),
            },
        )
