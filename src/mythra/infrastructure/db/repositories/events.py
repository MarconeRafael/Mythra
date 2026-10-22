"""Persistência append-only de eventos da história e consultas de leitura do histórico."""

from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from mythra.infrastructure.db.models import (
    CharacterKnowledge,
    CharacterRelationship,
    StateTransition,
    StoryEvent,
)

type EventRow = tuple[StoryEvent, UUID | None, UUID | None]


class StoryEventRepository:
    """Inserção e leitura; o banco rejeita UPDATE e DELETE de eventos por trigger (0010)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, *, story_id: UUID, values: dict[str, object]) -> StoryEvent:
        event = StoryEvent(story_id=story_id, **values)
        self.session.add(event)
        self.session.flush()
        self.session.refresh(event)
        return event

    def list_for_story(self, story_id: UUID) -> list[StoryEvent]:
        query = (
            select(StoryEvent)
            .where(StoryEvent.story_id == story_id)
            .order_by(StoryEvent.occurred_at, StoryEvent.sequence)
        )
        return list(self.session.scalars(query))

    def _with_origin(self) -> Any:
        """Evento com a transição que o aplicou e a execução de geração dela, se houver."""
        return select(StoryEvent, StateTransition.id, StateTransition.generation_run_id).outerjoin(
            StateTransition, StateTransition.applied_story_event_id == StoryEvent.id
        )

    def _rows(self, query: Any) -> list[EventRow]:
        return [cast("EventRow", tuple(row)) for row in self.session.execute(query)]

    def query(
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
    ) -> Sequence[EventRow]:
        query = self._with_origin().where(StoryEvent.story_id == story_id)
        if event_type is not None:
            query = query.where(StoryEvent.event_type == event_type)
        if aggregate_type is not None:
            query = query.where(StoryEvent.aggregate_type == aggregate_type)
        if aggregate_id is not None:
            query = query.where(StoryEvent.aggregate_id == aggregate_id)
        if source is not None:
            query = query.where(StoryEvent.source == source)
        if after_sequence is not None:
            query = query.where(StoryEvent.sequence > after_sequence)
        if up_to_sequence is not None:
            query = query.where(StoryEvent.sequence <= up_to_sequence)
        query = query.order_by(StoryEvent.sequence)
        if limit is not None:
            query = query.limit(limit)
        return self._rows(query)

    def query_for_character(self, story_id: UUID, character_id: UUID) -> Sequence[EventRow]:
        """Eventos do personagem e de suas relações e conhecimentos."""
        relationships = select(CharacterRelationship.id).where(
            CharacterRelationship.story_id == story_id,
            or_(
                CharacterRelationship.source_character_id == character_id,
                CharacterRelationship.target_character_id == character_id,
            ),
        )
        knowledge = select(CharacterKnowledge.id).where(
            CharacterKnowledge.story_id == story_id,
            CharacterKnowledge.character_id == character_id,
        )
        query = (
            self._with_origin()
            .where(
                StoryEvent.story_id == story_id,
                or_(
                    and_(
                        StoryEvent.aggregate_type == "character",
                        StoryEvent.aggregate_id == character_id,
                    ),
                    and_(
                        StoryEvent.aggregate_type == "relationship",
                        StoryEvent.aggregate_id.in_(relationships),
                    ),
                    and_(
                        StoryEvent.aggregate_type == "character_knowledge",
                        StoryEvent.aggregate_id.in_(knowledge),
                    ),
                ),
            )
            .order_by(StoryEvent.sequence)
        )
        return self._rows(query)

    def get(self, story_id: UUID, event_id: UUID) -> EventRow | None:
        rows = self._rows(
            self._with_origin().where(StoryEvent.story_id == story_id, StoryEvent.id == event_id)
        )
        return rows[0] if rows else None

    def get_for_transition(self, story_id: UUID, transition_id: UUID) -> EventRow | None:
        rows = self._rows(
            self._with_origin().where(
                StoryEvent.story_id == story_id, StateTransition.id == transition_id
            )
        )
        return rows[0] if rows else None
