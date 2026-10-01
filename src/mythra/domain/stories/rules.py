"""Invariantes de domínio da área de histórias."""

from dataclasses import dataclass
from uuid import UUID

from mythra.domain.exceptions import DomainRuleViolation


@dataclass(frozen=True)
class StoryState:
    """Identidade e requisitos mínimos de uma história persistente."""

    user_id: UUID
    title: str
    premise: str

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.premise.strip():
            raise DomainRuleViolation("Título e premissa da história são obrigatórios.")
