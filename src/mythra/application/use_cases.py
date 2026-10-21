"""Raiz de composição dos casos de uso da aplicação.

Mantém uma única superfície pública usada pelos routers, delegando cada
operação ao caso de uso especializado da respectiva área de domínio.
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from mythra.application.characters.ports import CharacterStore
from mythra.application.characters.use_cases import CharacterUseCases
from mythra.application.events.ports import StoryEventStore
from mythra.application.events.transitions import TransitionRecorder
from mythra.application.events.use_cases import EventUseCases
from mythra.application.narratives.ports import NarrativeStore
from mythra.application.narratives.use_cases import NarrativeUseCases
from mythra.application.state.ports import StateTransitionStore
from mythra.application.state.snapshot import StoryStateSnapshot
from mythra.application.state.transitions import StateTransitionUseCases
from mythra.application.state.use_cases import StoryStateUseCases
from mythra.application.stories.ports import StoryStore
from mythra.application.stories.use_cases import StoryUseCases
from mythra.application.transactions import UnitOfWork
from mythra.application.users.ports import UserStore
from mythra.application.users.use_cases import UserUseCases


class MythraUseCases:
    """Compõe os casos de uso por área atrás de uma única fachada."""

    def __init__(
        self,
        users: UserStore,
        stories: StoryStore,
        characters: CharacterStore,
        narratives: NarrativeStore,
        events: StoryEventStore,
        unit_of_work: UnitOfWork,
        state_transitions: StateTransitionStore,
    ) -> None:
        transitions = TransitionRecorder(events, stories, unit_of_work)
        self._users = UserUseCases(users, unit_of_work)
        self._stories = StoryUseCases(stories, self._users, unit_of_work)
        self._characters = CharacterUseCases(characters, self._stories, transitions, unit_of_work)
        self._narratives = NarrativeUseCases(narratives, self._stories, transitions, unit_of_work)
        self._events = EventUseCases(events, self._stories, unit_of_work)
        self._state = StoryStateUseCases(self._stories, stories, characters, narratives)
        self._state_transitions = StateTransitionUseCases(
            state_transitions,
            self._stories,
            self._characters,
            self._narratives,
            transitions,
            unit_of_work,
        )

    def propose_transition(self, story_id: UUID, **proposal: Any) -> Any:
        return self._state_transitions.propose(story_id, **proposal)

    def decide_transition(
        self, story_id: UUID, transition_id: UUID, *, approve: bool, decided_by_user_id: UUID | None
    ) -> Any:
        return self._state_transitions.decide(
            story_id, transition_id, approve=approve, decided_by_user_id=decided_by_user_id
        )

    def apply_transitions(
        self,
        story_id: UUID,
        transition_ids: Sequence[UUID],
        *,
        expected_state_version: int | None = None,
    ) -> list[Any]:
        return self._state_transitions.apply(
            story_id, transition_ids, expected_state_version=expected_state_version
        )

    def create_user(self, email: str, display_name: str) -> Any:
        return self._users.create_user(email, display_name)

    def get_user(self, user_id: UUID) -> Any:
        return self._users.get_user(user_id)

    def create_story(self, user_id: UUID, title: str, premise: str) -> Any:
        return self._stories.create_story(user_id, title, premise)

    def get_story(self, story_id: UUID) -> Any:
        return self._stories.get_story(story_id)

    def get_story_state(self, story_id: UUID) -> StoryStateSnapshot:
        return self._state.get_story_state(story_id)

    def update_story(self, story_id: UUID, changes: dict[str, str]) -> Any:
        return self._stories.update_story(story_id, changes)

    def create_preferences(self, story_id: UUID, tone: str) -> Any:
        return self._stories.create_preferences(story_id, tone)

    def get_preferences(self, story_id: UUID) -> Any:
        return self._stories.get_preferences(story_id)

    def create_character(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._characters.create_character(story_id, values)

    def update_character(
        self, story_id: UUID, character_id: UUID, updates: dict[str, Any]
    ) -> Any:
        return self._characters.update_character(story_id, character_id, updates)

    def list_characters(self, story_id: UUID) -> list[Any]:
        return self._characters.list_characters(story_id)

    def create_fact(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._characters.create_fact(story_id, values)

    def update_fact(self, story_id: UUID, fact_id: UUID, updates: dict[str, Any]) -> Any:
        return self._characters.update_fact(story_id, fact_id, updates)

    def list_facts(self, story_id: UUID) -> list[Any]:
        return self._characters.list_facts(story_id)

    def create_knowledge(self, story_id: UUID, character_id: UUID, values: dict[str, Any]) -> Any:
        return self._characters.create_knowledge(story_id, character_id, values)

    def update_knowledge(
        self, story_id: UUID, character_id: UUID, fact_id: UUID, updates: dict[str, Any]
    ) -> Any:
        return self._characters.update_knowledge(story_id, character_id, fact_id, updates)

    def list_knowledge(self, story_id: UUID, character_id: UUID) -> list[Any]:
        return self._characters.list_knowledge(story_id, character_id)

    def create_relationship(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._characters.create_relationship(story_id, values)

    def update_relationship(
        self, story_id: UUID, relationship_id: UUID, updates: dict[str, Any]
    ) -> Any:
        return self._characters.update_relationship(story_id, relationship_id, updates)

    def list_relationships(self, story_id: UUID) -> list[Any]:
        return self._characters.list_relationships(story_id)

    def create_timeline_event(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._narratives.create_timeline_event(story_id, values)

    def update_timeline_event(
        self, story_id: UUID, timeline_event_id: UUID, updates: dict[str, Any]
    ) -> Any:
        return self._narratives.update_timeline_event(story_id, timeline_event_id, updates)

    def list_timeline_events(self, story_id: UUID) -> list[Any]:
        return self._narratives.list_timeline_events(story_id)

    def create_plot_thread(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._narratives.create_plot_thread(story_id, values)

    def update_plot_thread(
        self, story_id: UUID, plot_thread_id: UUID, updates: dict[str, Any]
    ) -> Any:
        return self._narratives.update_plot_thread(story_id, plot_thread_id, updates)

    def list_plot_threads(self, story_id: UUID) -> list[Any]:
        return self._narratives.list_plot_threads(story_id)

    def create_arc(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._narratives.create_arc(story_id, values)

    def update_arc(self, story_id: UUID, arc_id: UUID, updates: dict[str, Any]) -> Any:
        return self._narratives.update_arc(story_id, arc_id, updates)

    def list_arcs(self, story_id: UUID) -> list[Any]:
        return self._narratives.list_arcs(story_id)

    def create_chapter(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._narratives.create_chapter(story_id, values)

    def update_chapter(self, story_id: UUID, chapter_id: UUID, updates: dict[str, Any]) -> Any:
        return self._narratives.update_chapter(story_id, chapter_id, updates)

    def list_chapters(self, story_id: UUID) -> list[Any]:
        return self._narratives.list_chapters(story_id)

    def record_story_event(self, story_id: UUID, values: dict[str, Any]) -> Any:
        return self._events.record_story_event(story_id, values)

    def list_story_events(self, story_id: UUID) -> list[Any]:
        return self._events.list_story_events(story_id)
