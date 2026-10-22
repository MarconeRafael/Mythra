"""Leitura do histórico de eventos e reconstrução histórica de relações."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from mythra.application.characters.ports import CharacterStore
from mythra.application.events.ports import StoryHistoryStore
from mythra.application.events.transitions import MANUAL_EVENT_OPERATION
from mythra.application.stories.use_cases import StoryUseCases
from mythra.core.exceptions import ResourceNotFoundError
from mythra.domain.events.reconstruction import (
    HistoricalEvent,
    HistoryReconstructionError,
    relationship_spec,
    replay,
)


@dataclass(frozen=True)
class StoryEventRecord:
    """Evento imutável, com a transição/execução de origem vindas da transição que o aplicou."""

    id: UUID
    story_id: UUID
    sequence: int
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    source: str
    operation: str
    payload: dict[str, Any]
    occurred_at: datetime
    state_transition_id: UUID | None
    generation_run_id: UUID | None


@dataclass(frozen=True)
class ReconstructedRelationship:
    """Estado histórico de uma relação, válido até `as_of_sequence`."""

    relationship_id: UUID
    story_id: UUID
    source_character_id: UUID
    target_character_id: UUID
    relationship_type: str
    trust: float
    status: str
    as_of_sequence: int
    last_event_id: UUID
    event_count: int


def _record(row: tuple[Any, UUID | None, UUID | None]) -> StoryEventRecord:
    event, transition_id, run_id = row
    return StoryEventRecord(
        id=event.id,
        story_id=event.story_id,
        sequence=event.sequence,
        event_type=event.event_type,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        source=event.source,
        operation=event.operation,
        payload=event.payload,
        occurred_at=event.occurred_at,
        state_transition_id=transition_id,
        generation_run_id=run_id,
    )


class StoryHistoryUseCases:
    """Consultas somente leitura sobre o log; o estado atual nunca depende delas."""

    def __init__(
        self, history: StoryHistoryStore, stories: StoryUseCases, characters: CharacterStore
    ) -> None:
        self.history = history
        self.stories = stories
        self.characters = characters

    def list_events(
        self,
        story_id: UUID,
        *,
        event_type: str | None = None,
        aggregate_type: str | None = None,
        aggregate_id: UUID | None = None,
        source: str | None = None,
        after_sequence: int | None = None,
        up_to_sequence: int | None = None,
        limit: int | None = None,
    ) -> list[StoryEventRecord]:
        """Eventos da história em ordem de sequência, com filtros opcionais."""
        self.stories.get_story(story_id)
        rows = self.history.query(
            story_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            source=source,
            after_sequence=after_sequence,
            up_to_sequence=up_to_sequence,
            limit=limit,
        )
        return [_record(row) for row in rows]

    def list_character_events(self, story_id: UUID, character_id: UUID) -> list[StoryEventRecord]:
        """Eventos do personagem, de suas relações e de seus conhecimentos."""
        if self.characters.get_in_story(story_id, character_id) is None:
            raise ResourceNotFoundError("Personagem não encontrada nesta história.")
        return [_record(row) for row in self.history.query_for_character(story_id, character_id)]

    def get_event(self, story_id: UUID, event_id: UUID) -> StoryEventRecord:
        row = self.history.get(story_id, event_id)
        if row is None:
            raise ResourceNotFoundError("Evento não encontrado nesta história.")
        return _record(row)

    def get_event_for_transition(self, story_id: UUID, transition_id: UUID) -> StoryEventRecord:
        """Evento que originou a mudança de estado aplicada por uma transição."""
        row = self.history.get_for_transition(story_id, transition_id)
        if row is None:
            raise ResourceNotFoundError("A transição não possui evento aplicado nesta história.")
        return _record(row)

    def reconstruct_relationship(
        self,
        story_id: UUID,
        relationship_id: UUID,
        *,
        up_to_sequence: int | None = None,
        initial_state: dict[str, Any] | None = None,
        verify_current: bool = False,
    ) -> ReconstructedRelationship:
        """Reconstrói a relação até `up_to_sequence` (ou o fim) a partir dos eventos.

        Eventos manuais (`record_story_event`) são anotações livres e não entram no replay.
        Sem evento de criação (relações anteriores ao log completo) é preciso informar
        `initial_state`. Com `verify_current`, o resultado é comparado com a linha atual.
        """
        if verify_current and up_to_sequence is not None:
            raise ValueError("`verify_current` exige a reconstrução até o último evento.")
        self.stories.get_story(story_id)
        rows = self.history.query(
            story_id,
            aggregate_type="relationship",
            aggregate_id=relationship_id,
            up_to_sequence=up_to_sequence,
        )
        events = [
            HistoricalEvent(event.id, event.sequence, event.event_type, event.payload)
            for event, _, _ in rows
            if event.operation != MANUAL_EVENT_OPERATION
        ]
        result = replay(events, relationship_spec(story_id), initial_state=initial_state)
        state = result.state
        reconstructed = ReconstructedRelationship(
            relationship_id=relationship_id,
            story_id=story_id,
            source_character_id=UUID(str(state["source_character_id"])),
            target_character_id=UUID(str(state["target_character_id"])),
            relationship_type=state["relationship_type"],
            trust=float(state["trust"]),
            status=state["status"],
            as_of_sequence=result.last_sequence,
            last_event_id=result.last_event_id,
            event_count=result.event_count,
        )
        if verify_current:
            self._verify_against_current(story_id, reconstructed)
        return reconstructed

    def _verify_against_current(
        self, story_id: UUID, reconstructed: ReconstructedRelationship
    ) -> None:
        current = self.characters.get_relationship_in_story(story_id, reconstructed.relationship_id)
        if current is None:
            raise HistoryReconstructionError("A relação reconstruída não existe no estado atual.")
        differences = [
            field
            for field in (
                "source_character_id",
                "target_character_id",
                "relationship_type",
                "trust",
                "status",
            )
            if getattr(current, field) != getattr(reconstructed, field)
        ]
        if differences:
            raise HistoryReconstructionError(
                f"O estado atual difere do histórico em {differences}: há mudança sem evento."
            )
