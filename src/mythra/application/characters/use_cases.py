"""Casos de uso de personagens, fatos, conhecimento e relacionamentos."""

from typing import Any
from uuid import UUID

from mythra.application.characters.ports import CharacterStore
from mythra.application.stories.use_cases import StoryUseCases
from mythra.core.exceptions import ResourceNotFoundError
from mythra.domain.characters.rules import CharacterKnowledgeState, RelationshipState


class CharacterUseCases:
    """Coordena personagens, fatos narrativos, conhecimento e relações."""

    def __init__(self, characters: CharacterStore, stories: StoryUseCases) -> None:
        self.characters = characters
        self.stories = stories

    def create_character(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        return self.characters.create(story_id=story_id, values=values)

    def list_characters(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.characters.list_for_story(story_id)

    def create_fact(self, story_id: UUID, values: dict[str, Any]) -> Any:
        self.stories.get_story(story_id)
        return self.characters.create_fact(story_id=story_id, values=values)

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
        return self.characters.create_knowledge(character_id=character_id, values=values)

    def list_knowledge(self, story_id: UUID, character_id: UUID) -> list[Any]:
        if self.characters.get_in_story(story_id, character_id) is None:
            raise ResourceNotFoundError("Personagem não encontrada nesta história.")
        return self.characters.list_knowledge(character_id)

    def create_relationship(self, story_id: UUID, values: dict[str, Any]) -> Any:
        RelationshipState(story_id=story_id, **values)
        return self.characters.create_relationship(story_id=story_id, values=values)

    def list_relationships(self, story_id: UUID) -> list[Any]:
        self.stories.get_story(story_id)
        return self.characters.list_relationships(story_id)
