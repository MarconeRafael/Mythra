"""Casos de uso de timeline, plot threads, arcos e capítulos."""

from typing import Any
from uuid import UUID

from mythra.application.narratives.ports import NarrativeStore
from mythra.application.stories.use_cases import StoryUseCases
from mythra.core.exceptions import ResourceNotFoundError
from mythra.domain.narratives.rules import ChapterPlacement, StoryArcState


class NarrativeUseCases:
    """Coordena eventos de timeline, plot threads, arcos e capítulos."""

    def __init__(self, narratives: NarrativeStore, stories: StoryUseCases) -> None:
        self.narratives = narratives
        self.stories = stories

    def create_timeline_event(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        return self.narratives.create_timeline_event(story_id=story_id, values=values)

    def list_timeline_events(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_timeline_events(story_id)

    def create_plot_thread(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        return self.narratives.create_plot_thread(story_id=story_id, values=values)

    def list_plot_threads(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_plot_threads(story_id)

    def create_arc(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        StoryArcState(
            story_id=story_id,
            title=values["title"],
            position=values["position"],
            status=values["status"],
            description=values.get("description"),
        )
        return self.narratives.create_arc(story_id=story_id, values=values)

    def list_arcs(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_arcs(story_id)

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
        return self.narratives.create_chapter(story_id=story_id, values=values)

    def list_chapters(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.narratives.list_chapters(story_id)
