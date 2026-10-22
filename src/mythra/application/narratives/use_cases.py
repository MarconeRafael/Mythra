"""Casos de uso de timeline, plot threads, arcos e capítulos."""

from typing import Any
from uuid import UUID

from mythra.application.events.transitions import (
    CHAPTER_CREATED,
    CHAPTER_UPDATED,
    PLOT_THREAD_CREATED,
    PLOT_THREAD_UPDATED,
    STORY_ARC_CREATED,
    STORY_ARC_UPDATED,
    TIMELINE_EVENT_CREATED,
    TIMELINE_EVENT_UPDATED,
    TransitionRecorder,
    UpdateTarget,
)
from mythra.application.narratives.ports import NarrativeStore
from mythra.application.stories.use_cases import StoryUseCases
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
    ) -> None:
        self.narratives = narratives
        self.stories = stories
        self.transitions = transitions

    def create_timeline_event(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        return self.transitions.create(
            story_id=story_id,
            values=values,
            event_type=TIMELINE_EVENT_CREATED,
            aggregate_type="timeline_event",
            operation="create_timeline_event",
            persist=lambda: self.narratives.create_timeline_event(story_id=story_id, values=values),
        )

    def list_timeline_events(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_timeline_events(story_id)

    def resolve_timeline_event_update(
        self, story_id: UUID, timeline_event_id: UUID
    ) -> UpdateTarget:
        record = self.narratives.get_timeline_event_in_story(story_id, timeline_event_id)
        if record is None:
            raise ResourceNotFoundError("Evento de timeline não encontrado nesta história.")
        return UpdateTarget(
            record=record,
            event_type=TIMELINE_EVENT_UPDATED,
            aggregate_type="timeline_event",
            operation="update_timeline_event",
            persist=self.narratives.update_timeline_event,
            validate=_no_extra_rules,
        )

    def update_timeline_event(
        self, story_id: UUID, timeline_event_id: UUID, updates: dict[str, Any]
    ) -> Any:
        target = self.resolve_timeline_event_update(story_id, timeline_event_id)
        return self.transitions.update(story_id=story_id, updates=updates, **target.as_kwargs())

    def create_plot_thread(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        return self.transitions.create(
            story_id=story_id,
            values=values,
            event_type=PLOT_THREAD_CREATED,
            aggregate_type="plot_thread",
            operation="create_plot_thread",
            persist=lambda: self.narratives.create_plot_thread(story_id=story_id, values=values),
        )

    def list_plot_threads(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_plot_threads(story_id)

    def resolve_plot_thread_update(self, story_id: UUID, plot_thread_id: UUID) -> UpdateTarget:
        record = self.narratives.get_plot_thread_in_story(story_id, plot_thread_id)
        if record is None:
            raise ResourceNotFoundError("Plot thread não encontrada nesta história.")
        return UpdateTarget(
            record=record,
            event_type=PLOT_THREAD_UPDATED,
            aggregate_type="plot_thread",
            operation="update_plot_thread",
            persist=self.narratives.update_plot_thread,
            validate=_no_extra_rules,
        )

    def update_plot_thread(
        self, story_id: UUID, plot_thread_id: UUID, updates: dict[str, Any]
    ) -> Any:
        target = self.resolve_plot_thread_update(story_id, plot_thread_id)
        return self.transitions.update(story_id=story_id, updates=updates, **target.as_kwargs())

    def create_arc(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        StoryArcState(
            story_id=story_id,
            title=values["title"],
            position=values["position"],
            status=values["status"],
            description=values.get("description"),
        )
        return self.transitions.create(
            story_id=story_id,
            values=values,
            event_type=STORY_ARC_CREATED,
            aggregate_type="story_arc",
            operation="create_arc",
            persist=lambda: self.narratives.create_arc(story_id=story_id, values=values),
        )

    def list_arcs(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_arcs(story_id)

    def resolve_arc_update(self, story_id: UUID, arc_id: UUID) -> UpdateTarget:
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

        return UpdateTarget(
            record=record,
            event_type=STORY_ARC_UPDATED,
            aggregate_type="story_arc",
            operation="update_arc",
            persist=self.narratives.update_arc,
            validate=validate,
        )

    def update_arc(self, story_id: UUID, arc_id: UUID, updates: dict[str, Any]) -> Any:
        target = self.resolve_arc_update(story_id, arc_id)
        return self.transitions.update(story_id=story_id, updates=updates, **target.as_kwargs())

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
        return self.transitions.create(
            story_id=story_id,
            values=values,
            event_type=CHAPTER_CREATED,
            aggregate_type="chapter",
            operation="create_chapter",
            persist=lambda: self.narratives.create_chapter(story_id=story_id, values=values),
        )

    def list_chapters(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_chapters(story_id)

    def resolve_chapter_update(self, story_id: UUID, chapter_id: UUID) -> UpdateTarget:
        record = self.narratives.get_chapter_in_story(story_id, chapter_id)
        if record is None:
            raise ResourceNotFoundError("Capítulo não encontrado nesta história.")
        return UpdateTarget(
            record=record,
            event_type=CHAPTER_UPDATED,
            aggregate_type="chapter",
            operation="update_chapter",
            persist=self.narratives.update_chapter,
            validate=_no_extra_rules,
        )

    def update_chapter(self, story_id: UUID, chapter_id: UUID, updates: dict[str, Any]) -> Any:
        target = self.resolve_chapter_update(story_id, chapter_id)
        return self.transitions.update(story_id=story_id, updates=updates, **target.as_kwargs())
