"""Persistência de eventos temporais, threads, arcos e capítulos."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from mythra.infrastructure.db.models import Chapter, PlotThread, StoryArc, TimelineEvent


class NarrativeRepository:
    """Operações explícitas para estruturas narrativas persistentes."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_timeline_event(self, *, story_id: UUID, values: dict[str, object]) -> TimelineEvent:
        record = TimelineEvent(story_id=story_id, **values)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list_timeline_events(self, story_id: UUID) -> list[TimelineEvent]:
        query = select(TimelineEvent).where(TimelineEvent.story_id == story_id).order_by(
            TimelineEvent.occurred_at
        )
        return list(self.session.scalars(query))

    def create_plot_thread(self, *, story_id: UUID, values: dict[str, object]) -> PlotThread:
        record = PlotThread(story_id=story_id, **values)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list_plot_threads(self, story_id: UUID) -> list[PlotThread]:
        return list(self.session.scalars(select(PlotThread).where(PlotThread.story_id == story_id)))

    def create_arc(self, *, story_id: UUID, values: dict[str, object]) -> StoryArc:
        record = StoryArc(story_id=story_id, **values)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list_arcs(self, story_id: UUID) -> list[StoryArc]:
        query = select(StoryArc).where(StoryArc.story_id == story_id).order_by(StoryArc.position)
        return list(self.session.scalars(query))

    def get_arc(self, arc_id: UUID) -> StoryArc | None:
        return self.session.get(StoryArc, arc_id)

    def create_chapter(self, *, story_id: UUID, values: dict[str, object]) -> Chapter:
        record = Chapter(story_id=story_id, **values)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list_chapters(self, story_id: UUID) -> list[Chapter]:
        query = select(Chapter).where(Chapter.story_id == story_id).order_by(
            Chapter.arc_id, Chapter.position
        )
        return list(self.session.scalars(query))
