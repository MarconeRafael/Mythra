"""Persistência de personagens, fatos, conhecimento e relações."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from mythra.infrastructure.db.models import (
    Character,
    CharacterKnowledge,
    CharacterRelationship,
    StoryFact,
)


class CharacterRepository:
    """Operações de persistência do estado e conhecimento das personagens."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, story_id: UUID, values: dict[str, object]) -> Character:
        character = Character(story_id=story_id, **values)
        self.session.add(character)
        self.session.commit()
        self.session.refresh(character)
        return character

    def list_for_story(self, story_id: UUID) -> list[Character]:
        return list(self.session.scalars(select(Character).where(Character.story_id == story_id)))

    def get_in_story(self, story_id: UUID, character_id: UUID) -> Character | None:
        return self.session.scalar(
            select(Character).where(
                Character.story_id == story_id,
                Character.id == character_id,
            )
        )

    def create_fact(self, *, story_id: UUID, values: dict[str, object]) -> StoryFact:
        fact = StoryFact(story_id=story_id, **values)
        self.session.add(fact)
        self.session.commit()
        self.session.refresh(fact)
        return fact

    def list_facts(self, story_id: UUID) -> list[StoryFact]:
        return list(self.session.scalars(select(StoryFact).where(StoryFact.story_id == story_id)))

    def get_fact_in_story(self, story_id: UUID, fact_id: UUID) -> StoryFact | None:
        query = select(StoryFact).where(
            StoryFact.story_id == story_id,
            StoryFact.id == fact_id,
        )
        return self.session.scalar(query)

    def create_knowledge(
        self, *, character_id: UUID, values: dict[str, object]
    ) -> CharacterKnowledge:
        knowledge = CharacterKnowledge(character_id=character_id, **values)
        self.session.add(knowledge)
        self.session.commit()
        self.session.refresh(knowledge)
        return knowledge

    def list_knowledge(self, character_id: UUID) -> list[CharacterKnowledge]:
        return list(
            self.session.scalars(
                select(CharacterKnowledge).where(CharacterKnowledge.character_id == character_id)
            )
        )

    def create_relationship(
        self, *, story_id: UUID, values: dict[str, object]
    ) -> CharacterRelationship:
        relationship = CharacterRelationship(story_id=story_id, **values)
        self.session.add(relationship)
        self.session.commit()
        self.session.refresh(relationship)
        return relationship

    def list_relationships(self, story_id: UUID) -> list[CharacterRelationship]:
        return list(
            self.session.scalars(
                select(CharacterRelationship).where(CharacterRelationship.story_id == story_id)
            )
        )
