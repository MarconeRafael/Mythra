"""Proposta, decisão e aplicação transacional de transições de estado canônico.

Gerações e edições só criam propostas; o estado canônico muda exclusivamente em `apply`,
que grava a mudança, o `StoryEvent` e o status `applied` na mesma transação.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from mythra.application.characters.use_cases import CharacterUseCases
from mythra.application.events.transitions import (
    CANONICAL_FACT_CREATED,
    CANONICAL_FACT_UPDATED,
    CHAPTER_UPDATED,
    CHARACTER_KNOWLEDGE_UPDATED,
    CHARACTER_STATE_UPDATED,
    PLOT_THREAD_UPDATED,
    RELATIONSHIP_UPDATED,
    STORY_ARC_UPDATED,
    TIMELINE_EVENT_UPDATED,
    TransitionRecorder,
    UpdateTarget,
    json_value,
)
from mythra.application.narratives.use_cases import NarrativeUseCases
from mythra.application.state.ports import StateTransitionStore
from mythra.application.stories.use_cases import StoryUseCases
from mythra.application.transactions import UnitOfWork, transaction
from mythra.core.exceptions import ConflictError, ResourceNotFoundError
from mythra.domain.exceptions import DomainRuleViolation

# (aggregate_type, operation) -> event_type emitido ao aplicar.
EVENT_TYPES: dict[tuple[str, str], str] = {
    ("character", "update"): CHARACTER_STATE_UPDATED,
    ("relationship", "update"): RELATIONSHIP_UPDATED,
    ("character_knowledge", "update"): CHARACTER_KNOWLEDGE_UPDATED,
    ("story_fact", "create"): CANONICAL_FACT_CREATED,
    ("story_fact", "update"): CANONICAL_FACT_UPDATED,
    ("timeline_event", "update"): TIMELINE_EVENT_UPDATED,
    ("plot_thread", "update"): PLOT_THREAD_UPDATED,
    ("story_arc", "update"): STORY_ARC_UPDATED,
    ("chapter", "update"): CHAPTER_UPDATED,
}
_DATETIME_FIELDS = frozenset({"known_at", "valid_from", "valid_to", "occurred_at"})
_FACT_REQUIRED_FIELDS = ("subject", "predicate", "object", "valid_from", "source")


class StaleTransitionError(ConflictError):
    """O estado canônico mudou desde a proposta; as propostas afetadas ficam `stale`."""

    def __init__(self, transition_ids: Sequence[UUID]) -> None:
        super().__init__("O estado canônico mudou desde que a transição foi proposta.")
        self.transition_ids = tuple(transition_ids)


def _from_json(field: str, value: Any) -> Any:
    if field in _DATETIME_FIELDS and isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def _changes_of(changes: Any) -> dict[str, dict[str, Any]]:
    body = changes.get("changes") if isinstance(changes, dict) else None
    if not isinstance(body, dict) or not body:
        raise DomainRuleViolation("`changes` deve conter ao menos um campo em `changes`.")
    for field, change in body.items():
        if not isinstance(change, dict) or set(change) != {"before", "after"}:
            raise DomainRuleViolation(f"`changes.{field}` deve conter apenas `before` e `after`.")
    return dict(body)


class StateTransitionUseCases:
    """Ciclo de vida de `state_transitions`: proposed -> approved/rejected -> applied/stale."""

    def __init__(
        self,
        transitions: StateTransitionStore,
        stories: StoryUseCases,
        characters: CharacterUseCases,
        narratives: NarrativeUseCases,
        recorder: TransitionRecorder,
        unit_of_work: UnitOfWork,
    ) -> None:
        self.transitions = transitions
        self.stories = stories
        self.characters = characters
        self.recorder = recorder
        self.unit_of_work = unit_of_work
        self._resolvers: dict[str, Callable[[UUID, UUID], UpdateTarget]] = {
            "character": characters.resolve_character_update,
            "relationship": characters.resolve_relationship_update,
            "character_knowledge": characters.resolve_knowledge_update_by_id,
            "story_fact": characters.resolve_fact_update,
            "timeline_event": narratives.resolve_timeline_event_update,
            "plot_thread": narratives.resolve_plot_thread_update,
            "story_arc": narratives.resolve_arc_update,
            "chapter": narratives.resolve_chapter_update,
        }

    def propose(
        self,
        story_id: UUID,
        *,
        generation_run_id: UUID | None,
        user_edit_id: UUID | None,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID | None,
        operation: str,
        changes: dict[str, Any],
        base_state_version: int,
    ) -> Any:
        """Registra a proposta; nenhuma tabela canônica é escrita."""
        self.stories.get_story(story_id)
        if (generation_run_id is None) == (user_edit_id is None):
            raise DomainRuleViolation("Informe exatamente uma origem: geração ou edição.")
        if EVENT_TYPES.get((aggregate_type, operation)) != event_type:
            raise DomainRuleViolation("Combinação inválida de agregado, operação e tipo de evento.")
        if operation == "update" and aggregate_id is None:
            raise DomainRuleViolation("Atualizações exigem `aggregate_id`.")
        body = _changes_of(changes)
        if operation == "create":
            missing = [f for f in _FACT_REQUIRED_FIELDS if f not in body]
            if missing:
                raise DomainRuleViolation(f"Campos obrigatórios ausentes: {', '.join(missing)}.")
        with transaction(self.unit_of_work):
            return self.transitions.create(
                story_id=story_id,
                values={
                    "generation_run_id": generation_run_id,
                    "user_edit_id": user_edit_id,
                    "event_type": event_type,
                    "aggregate_type": aggregate_type,
                    "aggregate_id": aggregate_id,
                    "operation": operation,
                    "changes": {"changes": body},
                    "base_state_version": base_state_version,
                },
            )

    def decide(
        self,
        story_id: UUID,
        transition_id: UUID,
        *,
        approve: bool,
        decided_by_user_id: UUID | None,
    ) -> Any:
        """Aprova ou rejeita uma proposta ainda `proposed`; decide no máximo uma vez."""
        with transaction(self.unit_of_work):
            changed = self.transitions.change_status(
                story_id=story_id,
                transition_id=transition_id,
                expected_statuses=("proposed",),
                values={
                    "status": "approved" if approve else "rejected",
                    "decided_by_user_id": decided_by_user_id,
                    "decided_at": datetime.now(UTC),
                },
            )
        return self._require_after_change(story_id, transition_id, changed)

    def apply(
        self,
        story_id: UUID,
        transition_ids: Sequence[UUID],
        *,
        expected_state_version: int | None = None,
    ) -> list[Any]:
        """Aplica propostas aprovadas, seus eventos e a nova versão em uma única transação."""
        ids = list(dict.fromkeys(transition_ids))
        try:
            with transaction(self.unit_of_work):
                current = self.transitions.lock_story_state_version(story_id)
                if current is None:
                    raise ResourceNotFoundError("História não encontrada.")
                if expected_state_version is not None and expected_state_version != current:
                    raise StaleTransitionError(ids)
                for transition_id in ids:
                    self._apply_one(story_id, transition_id)
        except StaleTransitionError as stale:
            self._mark_stale(story_id, stale.transition_ids)
            raise
        return [self._get(story_id, transition_id) for transition_id in ids]

    def _apply_one(self, story_id: UUID, transition_id: UUID) -> None:
        transition = self._get(story_id, transition_id)
        if transition.status != "approved":
            raise ConflictError("Somente transições aprovadas podem ser aplicadas.")
        body = _changes_of(transition.changes)
        after = {field: _from_json(field, change["after"]) for field, change in body.items()}
        if transition.operation == "update":
            resolver = self._resolvers[transition.aggregate_type]
            target = resolver(story_id, transition.aggregate_id)
            if target.event_type != transition.event_type:
                raise DomainRuleViolation("Tipo de evento incompatível com o agregado.")
            for field, change in body.items():
                if json_value(getattr(target.record, field)) != change["before"]:
                    raise StaleTransitionError([transition_id])
            staged = self.recorder.stage_update(
                story_id=story_id, updates=after, **target.as_kwargs()
            )
            if staged is None:
                raise DomainRuleViolation("A transição não produz mudança efetiva.")
            aggregate_id = transition.aggregate_id
        else:
            staged = self.characters.stage_fact_creation(story_id, after)
            aggregate_id = staged.record.id
        changed = self.transitions.change_status(
            story_id=story_id,
            transition_id=transition_id,
            expected_statuses=("approved",),
            values={
                "status": "applied",
                "aggregate_id": aggregate_id,
                "applied_at": datetime.now(UTC),
                "applied_story_event_id": staged.event.id,
            },
        )
        if not changed:
            raise ConflictError("A transição foi alterada por outra operação.")

    def _mark_stale(self, story_id: UUID, transition_ids: Sequence[UUID]) -> None:
        with transaction(self.unit_of_work):
            for transition_id in transition_ids:
                self.transitions.change_status(
                    story_id=story_id,
                    transition_id=transition_id,
                    expected_statuses=("proposed", "approved"),
                    values={"status": "stale"},
                )

    def _get(self, story_id: UUID, transition_id: UUID) -> Any:
        transition = self.transitions.get_in_story(story_id, transition_id)
        if transition is None:
            raise ResourceNotFoundError("Transição não encontrada nesta história.")
        return transition

    def _require_after_change(self, story_id: UUID, transition_id: UUID, changed: bool) -> Any:
        transition = self._get(story_id, transition_id)
        if not changed:
            raise ConflictError("A transição já foi decidida ou não está mais pendente.")
        return transition
