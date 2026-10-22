"""Casos de uso de personagens, fatos, conhecimento e relacionamentos."""

from typing import Any
from uuid import UUID

from mythra.application.characters.ports import CharacterStore
from mythra.application.events.transitions import (
    CANONICAL_FACT_CREATED,
    CANONICAL_FACT_UPDATED,
    CHARACTER_CREATED,
    CHARACTER_KNOWLEDGE_CREATED,
    CHARACTER_KNOWLEDGE_UPDATED,
    CHARACTER_STATE_UPDATED,
    RELATIONSHIP_CREATED,
    RELATIONSHIP_UPDATED,
    SOURCE_USER,
    StagedChange,
    TransitionRecorder,
    UpdateTarget,
)
from mythra.application.stories.use_cases import StoryUseCases
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
    ) -> None:
        self.characters = characters
        self.stories = stories
        self.transitions = transitions

    def create_character(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        return self.transitions.create(
            story_id=story_id,
            values=values,
            event_type=CHARACTER_CREATED,
            aggregate_type="character",
            operation="create_character",
            persist=lambda: self.characters.create(story_id=story_id, values=values),
        )

    def list_characters(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.characters.list_for_story(story_id)

    def resolve_character_update(self, story_id: UUID, character_id: UUID) -> UpdateTarget:
        character = self.characters.get_in_story(story_id, character_id)
        if character is None:
            raise ResourceNotFoundError("Personagem não encontrada nesta história.")
        return UpdateTarget(
            record=character,
            event_type=CHARACTER_STATE_UPDATED,
            aggregate_type="character",
            operation="update_character",
            persist=self.characters.update_character,
            validate=_no_extra_rules,
        )

    def update_character(self, story_id: UUID, character_id: UUID, updates: dict[str, Any]) -> Any:
        target = self.resolve_character_update(story_id, character_id)
        return self.transitions.update(story_id=story_id, updates=updates, **target.as_kwargs())

    def create_fact(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        return self.transitions.create(
            story_id=story_id,
            values=values,
            event_type=CANONICAL_FACT_CREATED,
            aggregate_type="story_fact",
            operation="create_fact",
            persist=lambda: self.characters.create_fact(story_id=story_id, values=values),
        )

    def stage_fact_creation(
        self,
        story_id: UUID,
        values: dict[str, Any],
        *,
        operation: str = "create_fact",
        source: str = SOURCE_USER,
    ) -> StagedChange:
        """Cria o fato e o evento `canonical_fact_created` na transação do chamador."""
        return self.transitions.stage_create(
            story_id=story_id,
            values=values,
            event_type=CANONICAL_FACT_CREATED,
            aggregate_type="story_fact",
            operation=operation,
            persist=lambda: self.characters.create_fact(story_id=story_id, values=values),
            source=source,
        )

    def resolve_fact_update(self, story_id: UUID, fact_id: UUID) -> UpdateTarget:
        fact = self.characters.get_fact_in_story(story_id, fact_id)
        if fact is None:
            raise ResourceNotFoundError("Fato não encontrado nesta história.")
        return UpdateTarget(
            record=fact,
            event_type=CANONICAL_FACT_UPDATED,
            aggregate_type="story_fact",
            operation="update_fact",
            persist=self.characters.update_fact,
            validate=_no_extra_rules,
        )

    def update_fact(self, story_id: UUID, fact_id: UUID, updates: dict[str, Any]) -> Any:
        target = self.resolve_fact_update(story_id, fact_id)
        return self.transitions.update(story_id=story_id, updates=updates, **target.as_kwargs())

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
        event_values = {k: v for k, v in values.items() if k != "story_id"}
        event_values["character_id"] = character_id
        return self.transitions.create(
            story_id=story_id,
            values=event_values,
            event_type=CHARACTER_KNOWLEDGE_CREATED,
            aggregate_type="character_knowledge",
            operation="create_knowledge",
            persist=lambda: self.characters.create_knowledge(
                character_id=character_id, values=values
            ),
        )

    def resolve_knowledge_update(
        self, story_id: UUID, character_id: UUID, fact_id: UUID
    ) -> UpdateTarget:
        knowledge = self.characters.get_knowledge_in_story(story_id, character_id, fact_id)
        if knowledge is None:
            raise ResourceNotFoundError("Conhecimento não encontrado nesta história.")
        return self._knowledge_target(knowledge)

    def resolve_knowledge_update_by_id(self, story_id: UUID, knowledge_id: UUID) -> UpdateTarget:
        knowledge = self.characters.get_knowledge_by_id_in_story(story_id, knowledge_id)
        if knowledge is None:
            raise ResourceNotFoundError("Conhecimento não encontrado nesta história.")
        return self._knowledge_target(knowledge)

    def _knowledge_target(self, knowledge: Any) -> UpdateTarget:
        character_id, fact_id = knowledge.character_id, knowledge.fact_id

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

        return UpdateTarget(
            record=knowledge,
            event_type=CHARACTER_KNOWLEDGE_UPDATED,
            aggregate_type="character_knowledge",
            operation="update_knowledge",
            persist=self.characters.update_knowledge,
            validate=validate,
        )

    def update_knowledge(
        self, story_id: UUID, character_id: UUID, fact_id: UUID, updates: dict[str, Any]
    ) -> Any:
        target = self.resolve_knowledge_update(story_id, character_id, fact_id)
        return self.transitions.update(story_id=story_id, updates=updates, **target.as_kwargs())

    def list_knowledge(self, story_id: UUID, character_id: UUID) -> list[Any]:
        if self.characters.get_in_story(story_id, character_id) is None:
            raise ResourceNotFoundError("Personagem não encontrada nesta história.")
        return self.characters.list_knowledge(character_id)

    def create_relationship(self, story_id: UUID, values: dict[str, Any]) -> Any:
        RelationshipState(story_id=story_id, **values)
        return self.transitions.create(
            story_id=story_id,
            values=values,
            event_type=RELATIONSHIP_CREATED,
            aggregate_type="relationship",
            operation="create_relationship",
            persist=lambda: self.characters.create_relationship(story_id=story_id, values=values),
        )

    def resolve_relationship_update(self, story_id: UUID, relationship_id: UUID) -> UpdateTarget:
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

        return UpdateTarget(
            record=relationship,
            event_type=RELATIONSHIP_UPDATED,
            aggregate_type="relationship",
            operation="update_relationship",
            persist=self.characters.update_relationship,
            validate=validate,
        )

    def update_relationship(
        self, story_id: UUID, relationship_id: UUID, updates: dict[str, Any]
    ) -> Any:
        target = self.resolve_relationship_update(story_id, relationship_id)
        return self.transitions.update(story_id=story_id, updates=updates, **target.as_kwargs())

    def list_relationships(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.characters.list_relationships(story_id)
