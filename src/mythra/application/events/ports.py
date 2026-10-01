"""Interface de persistência consumida pelo caso de uso de eventos."""

from typing import Any, Protocol
from uuid import UUID


class StoryEventStore(Protocol):
    def append(self, *, story_id: UUID, values: dict[str, Any]) -> Any: ...
    def list_for_story(self, story_id: UUID) -> list[Any]: ...
