"""Casos de uso de histórias e preferências narrativas."""

from typing import Any
from uuid import UUID

from mythra.application.events.transitions import (
    STORY_CREATED,
    STORY_PREFERENCES_CREATED,
    STORY_UPDATED,
    TransitionRecorder,
)
from mythra.application.stories.ports import StoryStore
from mythra.application.users.use_cases import UserUseCases
from mythra.core.exceptions import ResourceNotFoundError
from mythra.domain.stories.rules import StoryState


class StoryUseCases:
    """Coordena criação, atualização e preferências de uma história."""

    def __init__(
        self, stories: StoryStore, users: UserUseCases, transitions: TransitionRecorder
    ) -> None:
        self.stories = stories
        self.users = users
        self.transitions = transitions

    def create_story(self, user_id: UUID, title: str, premise: str) -> Any:
        self.users.get_user(user_id)
        StoryState(user_id=user_id, title=title, premise=premise)
        values = {"user_id": user_id, "title": title, "premise": premise}
        return self.transitions.create(
            story_id=None,  # o próprio registro criado é a história
            values=values,
            event_type=STORY_CREATED,
            aggregate_type="story",
            operation="create_story",
            persist=lambda: self.stories.create(user_id=user_id, title=title, premise=premise),
        )

    def get_story(self, story_id: UUID) -> Any:
        story = self.stories.get(story_id)
        if story is None:
            raise ResourceNotFoundError("História não encontrada.")
        return story

    def update_story(self, story_id: UUID, changes: dict[str, str]) -> Any:
        story = self.get_story(story_id)

        def validate(after: dict[str, Any]) -> None:
            merged = {"title": story.title, "premise": story.premise} | after
            StoryState(user_id=story.user_id, title=merged["title"], premise=merged["premise"])

        return self.transitions.update(
            story_id=story_id,
            record=story,
            updates=changes,
            event_type=STORY_UPDATED,
            aggregate_type="story",
            operation="update_story",
            persist=self.stories.update,
            validate=validate,
        )

    def create_preferences(self, story_id: UUID, tone: str) -> Any:
        self.get_story(story_id)
        return self.transitions.create(
            story_id=story_id,
            values={"tone": tone},
            event_type=STORY_PREFERENCES_CREATED,
            aggregate_type="story_preferences",
            operation="create_preferences",
            persist=lambda: self.stories.create_preferences(story_id=story_id, tone=tone),
        )

    def get_preferences(self, story_id: UUID) -> Any:
        self.get_story(story_id)
        preferences = self.stories.get_preferences(story_id)
        if preferences is None:
            raise ResourceNotFoundError("Preferências não encontradas.")
        return preferences
