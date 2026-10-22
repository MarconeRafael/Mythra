"""Reconstrução histórica de uma entidade a partir de eventos, sem consultar o estado atual.

O replay é estrito: exige criação (ou estado inicial conhecido), valida que o `before` de cada
campo coincide com o estado reconstruído até ali e falha explicitamente diante de lacunas ou
inconsistências, em vez de devolver um resultado parcial.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from mythra.domain.characters.rules import RelationshipState
from mythra.domain.exceptions import DomainRuleViolation


class HistoryReconstructionError(DomainRuleViolation):
    """O histórico não permite reconstruir um estado confiável."""


@dataclass(frozen=True)
class HistoricalEvent:
    event_id: UUID
    sequence: int
    event_type: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class EntitySpec:
    """Eventos e campos que compõem o histórico de um tipo de entidade."""

    create_event_type: str
    update_event_type: str
    required_fields: frozenset[str]
    update_fields: frozenset[str]
    validate: Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ReplayResult:
    state: dict[str, Any]
    last_sequence: int
    last_event_id: UUID
    event_count: int


def _fail(event: HistoricalEvent, reason: str) -> HistoryReconstructionError:
    return HistoryReconstructionError(
        f"Evento {event.event_id} (sequência {event.sequence}, {event.event_type}): {reason}"
    )


def _changes(event: HistoricalEvent) -> dict[str, dict[str, Any]]:
    body = event.payload.get("changes") if isinstance(event.payload, dict) else None
    if not isinstance(body, dict) or not body:
        raise _fail(event, "payload sem `changes` válido.")
    for field, change in body.items():
        if not isinstance(change, dict) or set(change) != {"before", "after"}:
            raise _fail(event, f"`changes.{field}` deve conter apenas `before` e `after`.")
    return body


def replay(
    events: Sequence[HistoricalEvent],
    spec: EntitySpec,
    *,
    initial_state: dict[str, Any] | None = None,
) -> ReplayResult:
    """Aplica os eventos em ordem de sequência sobre a criação ou o estado inicial informado."""
    if not events:
        raise HistoryReconstructionError("Nenhum evento disponível para reconstruir a entidade.")
    state = None if initial_state is None else dict(initial_state)
    previous_sequence = events[0].sequence - 1
    for event in events:
        if event.sequence <= previous_sequence:
            raise _fail(event, "sequência fora de ordem ou duplicada.")
        previous_sequence = event.sequence
        changes = _changes(event)
        if event.event_type == spec.create_event_type:
            if state is not None:
                raise _fail(event, "criação duplicada ou conflitante com o estado inicial.")
            if any(change["before"] is not None for change in changes.values()):
                raise _fail(event, "criação com `before` não nulo.")
            state = {field: change["after"] for field, change in changes.items()}
            missing = sorted(spec.required_fields - state.keys())
            if missing:
                raise _fail(event, f"criação sem os campos obrigatórios {missing}.")
        elif event.event_type == spec.update_event_type:
            if state is None:
                raise _fail(event, "atualização sem criação nem estado inicial (lacuna).")
            unknown = sorted(set(changes) - spec.update_fields)
            if unknown:
                raise _fail(event, f"campos não atualizáveis {unknown}.")
            for field, change in changes.items():
                if state.get(field) != change["before"]:
                    raise _fail(
                        event,
                        f"`{field}`: before={change['before']!r} difere do estado reconstruído "
                        f"{state.get(field)!r} (lacuna ou evento inconsistente).",
                    )
                state[field] = change["after"]
        else:
            raise _fail(event, "tipo de evento inesperado para esta entidade.")
        spec.validate(state)
    assert state is not None
    last = events[-1]
    return ReplayResult(state, last.sequence, last.event_id, len(events))


def relationship_spec(story_id: UUID) -> EntitySpec:
    """Histórico de `character_relationships`: criação e atualização de `trust`/`status`."""

    def validate(state: dict[str, Any]) -> None:
        try:
            RelationshipState(
                story_id=story_id,
                source_character_id=UUID(str(state["source_character_id"])),
                target_character_id=UUID(str(state["target_character_id"])),
                relationship_type=state["relationship_type"],
                trust=float(state["trust"]),
                status=state["status"],
            )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, DomainRuleViolation):
                raise HistoryReconstructionError(str(error)) from error
            raise HistoryReconstructionError(f"Estado reconstruído inválido: {error}") from error

    return EntitySpec(
        create_event_type="relationship_created",
        update_event_type="relationship_updated",
        required_fields=frozenset(
            {"source_character_id", "target_character_id", "relationship_type", "trust", "status"}
        ),
        update_fields=frozenset({"trust", "status"}),
        validate=validate,
    )
