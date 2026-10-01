"""Persistência append-only de eventos da história."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from mythra.infrastructure.db.models import StoryEvent


class StoryEventRepository:
    """Inserção e consulta cronológica sem operações de mutação ou remoção."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, *, story_id: UUID, values: dict[str, object]) -> StoryEvent:
        event = StoryEvent(story_id=story_id, **values)
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def list_for_story(self, story_id: UUID) -> list[StoryEvent]:
        query = select(StoryEvent).where(StoryEvent.story_id == story_id).order_by(
            StoryEvent.occurred_at
        )
        return list(self.session.scalars(query))
