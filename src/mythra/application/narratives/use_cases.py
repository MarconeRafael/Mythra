"""Casos de uso de timeline, plot threads, arcos e capítulos."""

from typing import Any
from uuid import UUID

from mythra.application.events.transitions import (
    CHAPTER_UPDATED,
    PLOT_THREAD_UPDATED,
    STORY_ARC_UPDATED,
    TIMELINE_EVENT_UPDATED,
    TransitionRecorder,
)
from mythra.application.narratives.ports import NarrativeStore
from mythra.application.stories.use_cases import StoryUseCases
from mythra.application.transactions import UnitOfWork, transaction
from mythra.core.exceptions import ResourceNotFoundError
from mythra.domain.narratives.rules import ChapterPlacement, StoryArcState


def _no_extra_rules(_: dict[str, Any]) -> None:
    """Campos desta transição não têm invariantes além do contrato da API."""


class NarrativeUseCases:
    """Coordena eventos de timeline, plot threads, arcos e capítulos."""

    def __init__(
        self,
        narratives: NarrativeStore,
        stories: StoryUseCases,
        transitions: TransitionRecorder,
        unit_of_work: UnitOfWork,
    ) -> None:
        self.narratives = narratives
        self.stories = stories
        self.transitions = transitions
        self.unit_of_work = unit_of_work

    def create_timeline_event(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        with transaction(self.unit_of_work):
            return self.narratives.create_timeline_event(story_id=story_id, values=values)

    def list_timeline_events(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_timeline_events(story_id)

    def update_timeline_event(
        self, story_id: UUID, timeline_event_id: UUID, updates: dict[str, Any]
    ) -> Any:
        record = self.narratives.get_timeline_event_in_story(story_id, timeline_event_id)
        if record is None:
            raise ResourceNotFoundError("Evento de timeline não encontrado nesta história.")
        return self.transitions.update(
            story_id=story_id,
            record=record,
            updates=updates,
            event_type=TIMELINE_EVENT_UPDATED,
            aggregate_type="timeline_event",
            persist=self.narratives.update_timeline_event,
            validate=_no_extra_rules,
        )

    def create_plot_thread(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        with transaction(self.unit_of_work):
            return self.narratives.create_plot_thread(story_id=story_id, values=values)

    def list_plot_threads(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_plot_threads(story_id)

    def update_plot_thread(
        self, story_id: UUID, plot_thread_id: UUID, updates: dict[str, Any]
    ) -> Any:
        record = self.narratives.get_plot_thread_in_story(story_id, plot_thread_id)
        if record is None:
            raise ResourceNotFoundError("Plot thread não encontrada nesta história.")
        return self.transitions.update(
            story_id=story_id,
            record=record,
            updates=updates,
            event_type=PLOT_THREAD_UPDATED,
            aggregate_type="plot_thread",
            persist=self.narratives.update_plot_thread,
            validate=_no_extra_rules,
        )

    def create_arc(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        StoryArcState(
            story_id=story_id,
            title=values["title"],
            position=values["position"],
            status=values["status"],
            description=values.get("description"),
        )
        with transaction(self.unit_of_work):
            return self.narratives.create_arc(story_id=story_id, values=values)

    def list_arcs(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_arcs(story_id)

    def update_arc(self, story_id: UUID, arc_id: UUID, updates: dict[str, Any]) -> Any:
        record = self.narratives.get_arc_in_story(story_id, arc_id)
        if record is None:
            raise ResourceNotFoundError("Arco não encontrado nesta história.")

        def validate(after: dict[str, Any]) -> None:
            merged = {
                "title": record.title,
                "description": record.description,
                "position": record.position,
                "status": record.status,
            } | after
            StoryArcState(story_id=story_id, **merged)

        return self.transitions.update(
            story_id=story_id,
            record=record,
            updates=updates,
            event_type=STORY_ARC_UPDATED,
            aggregate_type="story_arc",
            persist=self.narratives.update_arc,
            validate=validate,
        )

    def create_chapter(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        arc = self.narratives.get_arc(values["arc_id"])
        if arc is None:
            raise ResourceNotFoundError("Arco não encontrado.")
        ChapterPlacement(
            story_id=story_id,
            arc_story_id=arc.story_id,
            arc_id=values["arc_id"],
            position=values["position"],
        )
        with transaction(self.unit_of_work):
            return self.narratives.create_chapter(story_id=story_id, values=values)

    def list_chapters(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_chapters(story_id)

    def update_chapter(self, story_id: UUID, chapter_id: UUID, updates: dict[str, Any]) -> Any:
        record = self.narratives.get_chapter_in_story(story_id, chapter_id)
        if record is None:
            raise ResourceNotFoundError("Capítulo não encontrado nesta história.")
        return self.transitions.update(
            story_id=story_id,
            record=record,
            updates=updates,
            event_type=CHAPTER_UPDATED,
            aggregate_type="chapter",
            persist=self.narratives.update_chapter,
            validate=_no_extra_rules,
        )
