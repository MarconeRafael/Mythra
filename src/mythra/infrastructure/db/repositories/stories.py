"""Persistência de histórias e preferências."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from mythra.infrastructure.db.models import Story, StoryPreferences


class StoryRepository:
    """História e preferência um-para-um; o commit pertence à camada de aplicação."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, user_id: UUID, title: str, premise: str) -> Story:
        story = Story(user_id=user_id, title=title, premise=premise)
        self.session.add(story)
        self.session.flush()
        self.session.refresh(story)
        return story

    def get(self, story_id: UUID) -> Story | None:
        return self.session.get(Story, story_id)

    def update(self, story: Story, changes: dict[str, str]) -> Story:
        for field, value in changes.items():
            setattr(story, field, value)
        self.session.flush()
        self.session.refresh(story)
        return story

    def create_preferences(self, *, story_id: UUID, tone: str) -> StoryPreferences:
        preferences = StoryPreferences(story_id=story_id, tone=tone)
        self.session.add(preferences)
        self.session.flush()
        self.session.refresh(preferences)
        return preferences

    def get_preferences(self, story_id: UUID) -> StoryPreferences | None:
        query = select(StoryPreferences).where(StoryPreferences.story_id == story_id)
        return self.session.scalar(query)

    def lock_story(self, story_id: UUID) -> int | None:
        """Bloqueia a linha da história até o fim da transação, serializando as escritas dela."""
        version = self.session.scalar(
            select(Story.state_version).where(Story.id == story_id).with_for_update()
        )
        return None if version is None else int(version)

    def refresh(self, record: object) -> None:
        """Relê o registro no banco, descartando valores obsoletos da sessão."""
        self.session.refresh(record)

    def bump_state_version(self, story_id: UUID) -> int:
        """Incrementa atomicamente a versão do estado canônico dentro da transação corrente."""
        version = self.session.execute(
            update(Story)
            .where(Story.id == story_id)
            .values(state_version=Story.state_version + 1)
            .returning(Story.state_version)
        ).scalar_one()
        return int(version)
