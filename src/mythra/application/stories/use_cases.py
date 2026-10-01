"""Casos de uso de histórias e preferências narrativas."""

from typing import Any
from uuid import UUID

from mythra.application.stories.ports import StoryStore
from mythra.application.users.use_cases import UserUseCases
from mythra.core.exceptions import ResourceNotFoundError
from mythra.domain.stories.rules import StoryState


class StoryUseCases:
    """Coordena criação, atualização e preferências de uma história."""

    def __init__(self, stories: StoryStore, users: UserUseCases) -> None:
        self.stories = stories
        self.users = users

    def create_story(self, user_id: UUID, title: str, premise: str) -> Any:
        self.users.get_user(user_id)
        StoryState(user_id=user_id, title=title, premise=premise)
        return self.stories.create(user_id=user_id, title=title, premise=premise)

    def get_story(self, story_id: UUID) -> Any:
        story = self.stories.get(story_id)
        if story is None:
            raise ResourceNotFoundError("História não encontrada.")
        return story

    def update_story(self, story_id: UUID, changes: dict[str, str]) -> Any:
        return self.stories.update(self.get_story(story_id), changes)

    def create_preferences(self, story_id: UUID, tone: str) -> Any:
        self.get_story(story_id)
        return self.stories.create_preferences(story_id=story_id, tone=tone)

    def get_preferences(self, story_id: UUID) -> Any:
        self.get_story(story_id)
        preferences = self.stories.get_preferences(story_id)
        if preferences is None:
            raise ResourceNotFoundError("Preferências não encontradas.")
        return preferences
