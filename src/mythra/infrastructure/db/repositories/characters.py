"""Persistência de personagens, fatos, conhecimento e relações.

Os métodos apenas adicionam, alteram e fazem flush; commit e rollback pertencem
à fronteira transacional da camada de aplicação.
"""

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

    def _persist[T](self, record: T) -> T:
        self.session.add(record)
        self.session.flush()
        self.session.refresh(record)
        return record

    def _apply[T](self, record: T, changes: dict[str, object]) -> T:
        for field, value in changes.items():
            setattr(record, field, value)
        self.session.flush()
        self.session.refresh(record)
        return record

    def create(self, *, story_id: UUID, values: dict[str, object]) -> Character:
        return self._persist(Character(story_id=story_id, **values))

    def list_for_story(self, story_id: UUID) -> list[Character]:
        return list(self.session.scalars(select(Character).where(Character.story_id == story_id)))

    def get_in_story(self, story_id: UUID, character_id: UUID) -> Character | None:
        return self.session.scalar(
            select(Character).where(
                Character.story_id == story_id,
                Character.id == character_id,
            )
        )

    def update_character(self, character: Character, changes: dict[str, object]) -> Character:
        return self._apply(character, changes)

    def create_fact(self, *, story_id: UUID, values: dict[str, object]) -> StoryFact:
        return self._persist(StoryFact(story_id=story_id, **values))

    def list_facts(self, story_id: UUID) -> list[StoryFact]:
        return list(self.session.scalars(select(StoryFact).where(StoryFact.story_id == story_id)))

    def get_fact_in_story(self, story_id: UUID, fact_id: UUID) -> StoryFact | None:
        query = select(StoryFact).where(
            StoryFact.story_id == story_id,
            StoryFact.id == fact_id,
        )
        return self.session.scalar(query)

    def update_fact(self, fact: StoryFact, changes: dict[str, object]) -> StoryFact:
        return self._apply(fact, changes)

    def create_knowledge(
        self, *, character_id: UUID, values: dict[str, object]
    ) -> CharacterKnowledge:
        return self._persist(CharacterKnowledge(character_id=character_id, **values))

    def list_knowledge(self, character_id: UUID) -> list[CharacterKnowledge]:
        return list(
            self.session.scalars(
                select(CharacterKnowledge).where(CharacterKnowledge.character_id == character_id)
            )
        )

    def list_knowledge_for_story(self, story_id: UUID) -> list[CharacterKnowledge]:
        return list(
            self.session.scalars(
                select(CharacterKnowledge).where(CharacterKnowledge.story_id == story_id)
            )
        )

    def get_knowledge_in_story(
        self, story_id: UUID, character_id: UUID, fact_id: UUID
    ) -> CharacterKnowledge | None:
        return self.session.scalar(
            select(CharacterKnowledge).where(
                CharacterKnowledge.story_id == story_id,
                CharacterKnowledge.character_id == character_id,
                CharacterKnowledge.fact_id == fact_id,
            )
        )

    def update_knowledge(
        self, knowledge: CharacterKnowledge, changes: dict[str, object]
    ) -> CharacterKnowledge:
        return self._apply(knowledge, changes)

    def create_relationship(
        self, *, story_id: UUID, values: dict[str, object]
    ) -> CharacterRelationship:
        return self._persist(CharacterRelationship(story_id=story_id, **values))

    def list_relationships(self, story_id: UUID) -> list[CharacterRelationship]:
        return list(
            self.session.scalars(
                select(CharacterRelationship).where(CharacterRelationship.story_id == story_id)
            )
        )

    def get_relationship_in_story(
        self, story_id: UUID, relationship_id: UUID
    ) -> CharacterRelationship | None:
        return self.session.scalar(
            select(CharacterRelationship).where(
                CharacterRelationship.story_id == story_id,
                CharacterRelationship.id == relationship_id,
            )
        )

    def update_relationship(
        self, relationship: CharacterRelationship, changes: dict[str, object]
    ) -> CharacterRelationship:
        return self._apply(relationship, changes)
