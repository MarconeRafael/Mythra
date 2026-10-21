"""Persistência de propostas de transição de estado canônico; sem commit próprio."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from mythra.infrastructure.db.models import StateTransition, Story


class StateTransitionRepository:
    """Cria propostas e muda seu status condicionalmente (compare-and-set)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def lock_story_state_version(self, story_id: UUID) -> int | None:
        """Bloqueia a linha da história e devolve a versão atual do estado canônico."""
        query = select(Story.state_version).where(Story.id == story_id).with_for_update()
        version = self.session.scalar(query)
        return None if version is None else int(version)

    def create(self, *, story_id: UUID, values: dict[str, Any]) -> StateTransition:
        transition = StateTransition(story_id=story_id, **values)
        self.session.add(transition)
        self.session.flush()
        self.session.refresh(transition)
        return transition

    def get_in_story(self, story_id: UUID, transition_id: UUID) -> StateTransition | None:
        return self.session.scalar(
            select(StateTransition).where(
                StateTransition.story_id == story_id,
                StateTransition.id == transition_id,
            )
        )

    def change_status(
        self,
        *,
        story_id: UUID,
        transition_id: UUID,
        expected_statuses: Sequence[str],
        values: dict[str, Any],
    ) -> bool:
        """Atualiza somente se o status atual for o esperado; devolve se houve mudança."""
        result = self.session.execute(
            update(StateTransition)
            .where(
                StateTransition.story_id == story_id,
                StateTransition.id == transition_id,
                StateTransition.status.in_(list(expected_statuses)),
            )
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        return bool(result.rowcount == 1)  # type: ignore[attr-defined]
