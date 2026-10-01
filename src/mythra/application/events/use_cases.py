"""Caso de uso de registro e consulta do histórico append-only de eventos."""

from typing import Any
from uuid import UUID

from mythra.application.events.ports import StoryEventStore
from mythra.application.stories.use_cases import StoryUseCases


class EventUseCases:
    """Coordena o registro e a consulta cronológica de eventos de história."""

    def __init__(self, events: StoryEventStore, stories: StoryUseCases) -> None:
        self.events = events
        self.stories = stories

    def record_story_event(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        return self.events.append(story_id=story_id, values=values)

    def list_story_events(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.events.list_for_story(story_id)
