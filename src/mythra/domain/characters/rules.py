"""Invariantes de domínio da área de personagens, fatos e conhecimento."""

from dataclasses import dataclass
from uuid import UUID

from mythra.domain.exceptions import DomainRuleViolation


@dataclass(frozen=True)
class RelationshipState:
    """Estado atual direcionado entre duas personagens da mesma história."""

    story_id: UUID
    source_character_id: UUID
    target_character_id: UUID
    relationship_type: str
    trust: float
    status: str

    def __post_init__(self) -> None:
        if self.source_character_id == self.target_character_id:
            raise DomainRuleViolation("Uma personagem não pode se relacionar consigo mesma.")
        if not -1.0 <= self.trust <= 1.0:
            raise DomainRuleViolation("trust deve estar entre -1.0 e 1.0.")


@dataclass(frozen=True)
class CharacterKnowledgeState:
    """Conhecimento individual sobre um fato, com confiança delimitada."""

    character_id: UUID
    fact_id: UUID
    confidence: float
    visibility: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise DomainRuleViolation("confidence deve estar entre 0.0 e 1.0.")
