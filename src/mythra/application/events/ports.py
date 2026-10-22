"""Interfaces de persistência consumidas pelos casos de uso de eventos e de histórico."""

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID


class StoryEventStore(Protocol):
    def append(self, *, story_id: UUID, values: dict[str, Any]) -> Any: ...
    def list_for_story(self, story_id: UUID) -> list[Any]: ...


class StateVersionStore(Protocol):
    def lock_story(self, story_id: UUID) -> int | None: ...
    def bump_state_version(self, story_id: UUID) -> int: ...
    def refresh(self, record: Any) -> None: ...


class StoryHistoryStore(Protocol):
    """Leitura do log de eventos; cada item é `(evento, id_da_transição, id_da_execução)`."""

    def query(
        self,
        story_id: UUID,
        *,
        event_type: str | None = None,
        aggregate_type: str | None = None,
        aggregate_id: UUID | None = None,
        source: str | None = None,
        after_sequence: int | None = None,
        up_to_sequence: int | None = None,
        limit: int | None = None,
    ) -> Sequence[tuple[Any, UUID | None, UUID | None]]: ...

    def query_for_character(
        self, story_id: UUID, character_id: UUID
    ) -> Sequence[tuple[Any, UUID | None, UUID | None]]: ...

    def get(
        self, story_id: UUID, event_id: UUID
    ) -> tuple[Any, UUID | None, UUID | None] | None: ...

    def get_for_transition(
        self, story_id: UUID, transition_id: UUID
    ) -> tuple[Any, UUID | None, UUID | None] | None: ...
