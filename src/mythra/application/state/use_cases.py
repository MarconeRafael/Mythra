"""Caso de uso que monta o snapshot do estado canônico a partir das entidades normalizadas."""

from dataclasses import fields
from typing import TYPE_CHECKING, Any
from uuid import UUID

from mythra.application.characters.ports import CharacterStore
from mythra.application.narratives.ports import NarrativeStore
from mythra.application.state.snapshot import (
    ArcSnapshot,
    ChapterSnapshot,
    CharacterSnapshot,
    FactSnapshot,
    KnowledgeSnapshot,
    PlotThreadSnapshot,
    PreferencesSnapshot,
    RelationshipSnapshot,
    StorySnapshot,
    StoryStateSnapshot,
    TimelineEventSnapshot,
)
from mythra.application.stories.ports import StoryStore
from mythra.application.stories.use_cases import StoryUseCases

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


def _copy[T: DataclassInstance](snapshot_type: type[T], row: Any) -> T:
    values = {field.name: getattr(row, field.name) for field in fields(snapshot_type)}
    return snapshot_type(**values)


class StoryStateUseCases:
    """Leitura somente do estado atual; não grava eventos nem cria cache."""

    def __init__(
        self,
        stories: StoryUseCases,
        story_store: StoryStore,
        characters: CharacterStore,
        narratives: NarrativeStore,
    ) -> None:
        self.stories = stories
        self.story_store = story_store
        self.characters = characters
        self.narratives = narratives

    def get_story_state(self, story_id: UUID) -> StoryStateSnapshot:
        story = self.stories.get_story(story_id)
        preferences = self.story_store.get_preferences(story_id)
        return StoryStateSnapshot(
            story=_copy(StorySnapshot, story),
            preferences=_copy(PreferencesSnapshot, preferences) if preferences else None,
            characters=tuple(
                _copy(CharacterSnapshot, row) for row in self.characters.list_for_story(story_id)
            ),
            relationships=tuple(
                _copy(RelationshipSnapshot, row)
                for row in self.characters.list_relationships(story_id)
            ),
            facts=tuple(_copy(FactSnapshot, row) for row in self.characters.list_facts(story_id)),
            knowledge=tuple(
                _copy(KnowledgeSnapshot, row)
                for row in self.characters.list_knowledge_for_story(story_id)
            ),
            timeline_events=tuple(
                _copy(TimelineEventSnapshot, row)
                for row in self.narratives.list_timeline_events(story_id)
            ),
            plot_threads=tuple(
                _copy(PlotThreadSnapshot, row)
                for row in self.narratives.list_plot_threads(story_id)
            ),
            arcs=tuple(_copy(ArcSnapshot, row) for row in self.narratives.list_arcs(story_id)),
            chapters=tuple(
                _copy(ChapterSnapshot, row) for row in self.narratives.list_chapters(story_id)
            ),
        )
