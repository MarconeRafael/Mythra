"""Casos de uso de personagens, fatos, conhecimento e relacionamentos."""

from typing import Any
from uuid import UUID

from mythra.application.characters.ports import CharacterStore
from mythra.application.events.transitions import (
    CANONICAL_FACT_CREATED,
    CANONICAL_FACT_UPDATED,
    CHARACTER_KNOWLEDGE_UPDATED,
    CHARACTER_STATE_UPDATED,
    RELATIONSHIP_UPDATED,
    TransitionRecorder,
)
from mythra.application.stories.use_cases import StoryUseCases
from mythra.application.transactions import UnitOfWork, transaction
from mythra.core.exceptions import ResourceNotFoundError
from mythra.domain.characters.rules import CharacterKnowledgeState, RelationshipState


def _no_extra_rules(_: dict[str, Any]) -> None:
    """Campos desta transição não têm invariantes além do contrato da API."""


class CharacterUseCases:
    """Coordena personagens, fatos narrativos, conhecimento e relações."""

    def __init__(
        self,
        characters: CharacterStore,
        stories: StoryUseCases,
        transitions: TransitionRecorder,
        unit_of_work: UnitOfWork,
    ) -> None:
        self.characters = characters
        self.stories = stories
        self.transitions = transitions
        self.unit_of_work = unit_of_work

    def create_character(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        with transaction(self.unit_of_work):
            return self.characters.create(story_id=story_id, values=values)

    def list_characters(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.characters.list_for_story(story_id)

    def update_character(
        self, story_id: UUID, character_id: UUID, updates: dict[str, Any]
    ) -> Any:
        character = self.characters.get_in_story(story_id, character_id)
        if character is None:
            raise ResourceNotFoundError("Personagem não encontrada nesta história.")
        return self.transitions.update(
            story_id=story_id,
            record=character,
            updates=updates,
            event_type=CHARACTER_STATE_UPDATED,
            aggregate_type="character",
            persist=self.characters.update_character,
            validate=_no_extra_rules,
        )

    def create_fact(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        return self.transitions.create(
            story_id=story_id,
            values=values,
            event_type=CANONICAL_FACT_CREATED,
            aggregate_type="story_fact",
            persist=lambda: self.characters.create_fact(story_id=story_id, values=values),
        )

    def update_fact(self, story_id: UUID, fact_id: UUID, updates: dict[str, Any]) -> Any:
        fact = self.characters.get_fact_in_story(story_id, fact_id)
        if fact is None:
            raise ResourceNotFoundError("Fato não encontrado nesta história.")
        return self.transitions.update(
            story_id=story_id,
            record=fact,
            updates=updates,
            event_type=CANONICAL_FACT_UPDATED,
            aggregate_type="story_fact",
            persist=self.characters.update_fact,
            validate=_no_extra_rules,
        )

    def list_facts(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.characters.list_facts(story_id)

    def create_knowledge(self, story_id: UUID, character_id: UUID, values: dict[str, Any]) -> Any:
        if self.characters.get_in_story(story_id, character_id) is None:
            raise ResourceNotFoundError("Personagem não encontrada nesta história.")
        if self.characters.get_fact_in_story(story_id, values["fact_id"]) is None:
            raise ResourceNotFoundError("Fato não encontrado nesta história.")
        CharacterKnowledgeState(
            character_id=character_id,
            fact_id=values["fact_id"],
            confidence=values["confidence"],
            visibility=values["visibility"],
        )
        with transaction(self.unit_of_work):
            return self.characters.create_knowledge(character_id=character_id, values=values)

    def update_knowledge(
        self, story_id: UUID, character_id: UUID, fact_id: UUID, updates: dict[str, Any]
    ) -> Any:
        knowledge = self.characters.get_knowledge_in_story(story_id, character_id, fact_id)
        if knowledge is None:
            raise ResourceNotFoundError("Conhecimento não encontrado nesta história.")

        def validate(after: dict[str, Any]) -> None:
            merged = {
                "confidence": knowledge.confidence,
                "visibility": knowledge.visibility,
            } | after
            CharacterKnowledgeState(
                character_id=character_id,
                fact_id=fact_id,
                confidence=merged["confidence"],
                visibility=merged["visibility"],
            )

        return self.transitions.update(
            story_id=story_id,
            record=knowledge,
            updates=updates,
            event_type=CHARACTER_KNOWLEDGE_UPDATED,
            aggregate_type="character_knowledge",
            persist=self.characters.update_knowledge,
            validate=validate,
        )

    def list_knowledge(self, story_id: UUID, character_id: UUID) -> list[Any]:
        if self.characters.get_in_story(story_id, character_id) is None:
            raise ResourceNotFoundError("Personagem não encontrada nesta história.")
        return self.characters.list_knowledge(character_id)

    def create_relationship(self, story_id: UUID, values: dict[str, Any]) -> Any:
        RelationshipState(story_id=story_id, **values)
        with transaction(self.unit_of_work):
            return self.characters.create_relationship(story_id=story_id, values=values)

    def update_relationship(
        self, story_id: UUID, relationship_id: UUID, updates: dict[str, Any]
    ) -> Any:
        relationship = self.characters.get_relationship_in_story(story_id, relationship_id)
        if relationship is None:
            raise ResourceNotFoundError("Relacionamento não encontrado nesta história.")

        def validate(after: dict[str, Any]) -> None:
            merged = {"trust": relationship.trust, "status": relationship.status} | after
            RelationshipState(
                story_id=story_id,
                source_character_id=relationship.source_character_id,
                target_character_id=relationship.target_character_id,
                relationship_type=relationship.relationship_type,
                trust=merged["trust"],
                status=merged["status"],
            )

        return self.transitions.update(
            story_id=story_id,
            record=relationship,
            updates=updates,
            event_type=RELATIONSHIP_UPDATED,
            aggregate_type="relationship",
            persist=self.characters.update_relationship,
            validate=validate,
        )

    def list_relationships(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.characters.list_relationships(story_id)
