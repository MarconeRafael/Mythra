"""Raiz de composição dos casos de uso da Fase 01.

Mantém a mesma superfície pública usada pelos routers, delegando cada
operação ao caso de uso especializado da respectiva área de domínio.
"""

from typing import Any
from uuid import UUID

from mythra.application.characters.ports import CharacterStore
from mythra.application.characters.use_cases import CharacterUseCases
from mythra.application.events.ports import StoryEventStore
from mythra.application.events.use_cases import EventUseCases
from mythra.application.narratives.ports import NarrativeStore
from mythra.application.narratives.use_cases import NarrativeUseCases
from mythra.application.stories.ports import StoryStore
from mythra.application.stories.use_cases import StoryUseCases
from mythra.application.users.ports import UserStore
from mythra.application.users.use_cases import UserUseCases


class MythraUseCases:
    """Compõe os casos de uso por área atrás de uma única fachada."""

    def __init__(
        self,
        users: UserStore,
        stories: StoryStore,
        characters: CharacterStore,
        narratives: NarrativeStore,
        events: StoryEventStore,
    ) -> None:
        self._users = UserUseCases(users)
        self._stories = StoryUseCases(stories, self._users)
        self._characters = CharacterUseCases(characters, self._stories)
        self._narratives = NarrativeUseCases(narratives, self._stories)
        self._events = EventUseCases(events, self._stories)

    def create_user(self, email: str, display_name: str) -> Any:
        return self._users.create_user(email, display_name)

    def get_user(self, user_id: UUID) -> Any:
        return self._users.get_user(user_id)

    def create_story(self, user_id: UUID, title: str, premise: str) -> Any:
        return self._stories.create_story(user_id, title, premise)

    def get_story(self, story_id: UUID) -> Any:
        return self._stories.get_story(story_id)

    def update_story(self, story_id: UUID, changes: dict[str, str]) -> Any:
        return self._stories.update_story(story_id, changes)

    def create_preferences(self, story_id: UUID, tone: str) -> Any:
        return self._stories.create_preferences(story_id, tone)

    def get_preferences(self, story_id: UUID) -> Any:
        return self._stories.get_preferences(story_id)

    def create_character(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._characters.create_character(story_id, values)

    def list_characters(self, story_id: UUID) -> list[Any]:
        return self._characters.list_characters(story_id)

    def create_fact(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._characters.create_fact(story_id, values)

    def list_facts(self, story_id: UUID) -> list[Any]:
        return self._characters.list_facts(story_id)

    def create_knowledge(self, story_id: UUID, character_id: UUID, values: dict[str, Any]) -> Any:
        return self._characters.create_knowledge(story_id, character_id, values)

    def list_knowledge(self, story_id: UUID, character_id: UUID) -> list[Any]:
        return self._characters.list_knowledge(story_id, character_id)

    def create_relationship(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._characters.create_relationship(story_id, values)

    def list_relationships(self, story_id: UUID) -> list[Any]:
        return self._characters.list_relationships(story_id)

    def create_timeline_event(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._narratives.create_timeline_event(story_id, values)

    def list_timeline_events(self, story_id: UUID) -> list[Any]:
        return self._narratives.list_timeline_events(story_id)

    def create_plot_thread(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._narratives.create_plot_thread(story_id, values)

    def list_plot_threads(self, story_id: UUID) -> list[Any]:
        return self._narratives.list_plot_threads(story_id)

    def create_arc(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._narratives.create_arc(story_id, values)

    def list_arcs(self, story_id: UUID) -> list[Any]:
        return self._narratives.list_arcs(story_id)

    def create_chapter(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._narratives.create_chapter(story_id, values)

    def list_chapters(self, story_id: UUID) -> list[Any]:
        return self._narratives.list_chapters(story_id)

    def record_story_event(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._events.record_story_event(story_id, values)

    def list_story_events(self, story_id: UUID) -> list[Any]:
        return self._events.list_story_events(story_id)
