"""Caso de uso de registro e consulta do histórico append-only de eventos."""

from typing import Any
from uuid import UUID

from mythra.application.events.ports import StoryEventStore
from mythra.application.events.transitions import MANUAL_EVENT_OPERATION, SOURCE_USER
from mythra.application.stories.use_cases import StoryUseCases
from mythra.application.transactions import UnitOfWork, transaction


class EventUseCases:
    """Coordena o registro e a consulta cronológica de eventos de história."""

    def __init__(
        self, events: StoryEventStore, stories: StoryUseCases, unit_of_work: UnitOfWork
    ) -> None:
        self.events = events
        self.stories = stories
        self.unit_of_work = unit_of_work

    def record_story_event(self, story_id: UUID, values: dict[str, Any]) -> Any:
        """Registra uma anotação livre; não altera estado nem entra na reconstrução histórica."""
        self.stories.get_story(story_id)
        values = values | {"source": SOURCE_USER, "operation": MANUAL_EVENT_OPERATION}
        with transaction(self.unit_of_work):
            return self.events.append(story_id=story_id, values=values)

    def list_story_events(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.events.list_for_story(story_id)
