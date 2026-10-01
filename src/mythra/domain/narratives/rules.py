"""Invariantes de domínio da área de arcos, capítulos, timeline e threads."""

from dataclasses import dataclass
from uuid import UUID

from mythra.domain.exceptions import DomainRuleViolation


@dataclass(frozen=True)
class StoryArcState:
    """Identidade narrativa de um arco sem impor uma sequência numérica."""

    story_id: UUID
    title: str
    position: int
    status: str
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.status.strip():
            raise DomainRuleViolation("Título e estado do arco são obrigatórios.")


@dataclass(frozen=True)
class ChapterPlacement:
    """Vínculo que garante que capítulo e arco pertencem à mesma história."""

    story_id: UUID
    arc_story_id: UUID
    arc_id: UUID
    position: int

    def __post_init__(self) -> None:
        if self.story_id != self.arc_story_id:
            raise DomainRuleViolation("O capítulo e o arco devem pertencer à mesma história.")
