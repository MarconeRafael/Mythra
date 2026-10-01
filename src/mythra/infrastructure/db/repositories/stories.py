"""Persistência de histórias e preferências."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from mythra.infrastructure.db.models import Story, StoryPreferences


class StoryRepository:
    """Operações de história e de sua preferência um-para-um."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, user_id: UUID, title: str, premise: str) -> Story:
        story = Story(user_id=user_id, title=title, premise=premise)
        self.session.add(story)
        self.session.commit()
        self.session.refresh(story)
        return story

    def get(self, story_id: UUID) -> Story | None:
        return self.session.get(Story, story_id)

    def update(self, story: Story, changes: dict[str, str]) -> Story:
        for field, value in changes.items():
            setattr(story, field, value)
        self.session.commit()
        self.session.refresh(story)
        return story

    def create_preferences(self, *, story_id: UUID, tone: str) -> StoryPreferences:
        preferences = StoryPreferences(story_id=story_id, tone=tone)
        self.session.add(preferences)
        self.session.commit()
        self.session.refresh(preferences)
        return preferences

    def get_preferences(self, story_id: UUID) -> StoryPreferences | None:
        query = select(StoryPreferences).where(StoryPreferences.story_id == story_id)
        return self.session.scalar(query)
