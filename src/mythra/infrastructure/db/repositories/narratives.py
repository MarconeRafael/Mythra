"""Persistência de eventos temporais, threads, arcos e capítulos.

Os métodos apenas adicionam, alteram e fazem flush; commit e rollback pertencem
à fronteira transacional da camada de aplicação.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from mythra.infrastructure.db.models import Chapter, PlotThread, StoryArc, TimelineEvent


class NarrativeRepository:
    """Operações explícitas para estruturas narrativas persistentes."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _persist[T](self, record: T) -> T:
        self.session.add(record)
        self.session.flush()
        self.session.refresh(record)
        return record

    def _apply[T](self, record: T, changes: dict[str, object]) -> T:
        for field, value in changes.items():
            setattr(record, field, value)
        self.session.flush()
        self.session.refresh(record)
        return record

    def create_timeline_event(self, *, story_id: UUID, values: dict[str, object]) -> TimelineEvent:
        return self._persist(TimelineEvent(story_id=story_id, **values))

    def list_timeline_events(self, story_id: UUID) -> list[TimelineEvent]:
        query = select(TimelineEvent).where(TimelineEvent.story_id == story_id).order_by(
            TimelineEvent.occurred_at
        )
        return list(self.session.scalars(query))

    def get_timeline_event_in_story(
        self, story_id: UUID, timeline_event_id: UUID
    ) -> TimelineEvent | None:
        return self.session.scalar(
            select(TimelineEvent).where(
                TimelineEvent.story_id == story_id,
                TimelineEvent.id == timeline_event_id,
            )
        )

    def update_timeline_event(
        self, record: TimelineEvent, changes: dict[str, object]
    ) -> TimelineEvent:
        return self._apply(record, changes)

    def create_plot_thread(self, *, story_id: UUID, values: dict[str, object]) -> PlotThread:
        return self._persist(PlotThread(story_id=story_id, **values))

    def list_plot_threads(self, story_id: UUID) -> list[PlotThread]:
        return list(self.session.scalars(select(PlotThread).where(PlotThread.story_id == story_id)))

    def get_plot_thread_in_story(self, story_id: UUID, plot_thread_id: UUID) -> PlotThread | None:
        return self.session.scalar(
            select(PlotThread).where(
                PlotThread.story_id == story_id,
                PlotThread.id == plot_thread_id,
            )
        )

    def update_plot_thread(self, record: PlotThread, changes: dict[str, object]) -> PlotThread:
        return self._apply(record, changes)

    def create_arc(self, *, story_id: UUID, values: dict[str, object]) -> StoryArc:
        return self._persist(StoryArc(story_id=story_id, **values))

    def list_arcs(self, story_id: UUID) -> list[StoryArc]:
        query = select(StoryArc).where(StoryArc.story_id == story_id).order_by(StoryArc.position)
        return list(self.session.scalars(query))

    def get_arc(self, arc_id: UUID) -> StoryArc | None:
        return self.session.get(StoryArc, arc_id)

    def get_arc_in_story(self, story_id: UUID, arc_id: UUID) -> StoryArc | None:
        return self.session.scalar(
            select(StoryArc).where(StoryArc.story_id == story_id, StoryArc.id == arc_id)
        )

    def update_arc(self, record: StoryArc, changes: dict[str, object]) -> StoryArc:
        return self._apply(record, changes)

    def create_chapter(self, *, story_id: UUID, values: dict[str, object]) -> Chapter:
        return self._persist(Chapter(story_id=story_id, **values))

    def list_chapters(self, story_id: UUID) -> list[Chapter]:
        query = select(Chapter).where(Chapter.story_id == story_id).order_by(
            Chapter.arc_id, Chapter.position
        )
        return list(self.session.scalars(query))

    def get_chapter_in_story(self, story_id: UUID, chapter_id: UUID) -> Chapter | None:
        return self.session.scalar(
            select(Chapter).where(Chapter.story_id == story_id, Chapter.id == chapter_id)
        )

    def update_chapter(self, record: Chapter, changes: dict[str, object]) -> Chapter:
        # Toda mudança efetiva incrementa a revisão usada no lock otimista de edições.
        return self._apply(record, {**changes, "revision": record.revision + 1})
