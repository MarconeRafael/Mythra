"""Rotas para personagens, fatos, conhecimento e relacionamentos."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from mythra.api.dependencies import get_use_cases
from mythra.api.schemas import (
    CharacterCreate,
    CharacterKnowledgeCreate,
    CharacterKnowledgeRead,
    CharacterRead,
    CharacterRelationshipCreate,
    CharacterRelationshipRead,
    StoryFactCreate,
    StoryFactRead,
)
from mythra.application.use_cases import MythraUseCases

router = APIRouter(prefix="/stories/{story_id}", tags=["characters"])
UseCases = Annotated[MythraUseCases, Depends(get_use_cases)]


@router.post("/characters", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
def create_character(
    story_id: UUID, payload: CharacterCreate, use_cases: UseCases
) -> CharacterRead:
    return CharacterRead.model_validate(use_cases.create_character(story_id, payload.model_dump()))


@router.get("/characters", response_model=list[CharacterRead])
def list_characters(story_id: UUID, use_cases: UseCases) -> list[CharacterRead]:
    return [CharacterRead.model_validate(item) for item in use_cases.list_characters(story_id)]


@router.post("/facts", response_model=StoryFactRead, status_code=status.HTTP_201_CREATED)
def create_fact(story_id: UUID, payload: StoryFactCreate, use_cases: UseCases) -> StoryFactRead:
    return StoryFactRead.model_validate(use_cases.create_fact(story_id, payload.model_dump()))


@router.get("/facts", response_model=list[StoryFactRead])
def list_facts(story_id: UUID, use_cases: UseCases) -> list[StoryFactRead]:
    return [StoryFactRead.model_validate(item) for item in use_cases.list_facts(story_id)]


@router.post(
    "/characters/{character_id}/knowledge",
    response_model=CharacterKnowledgeRead,
    status_code=status.HTTP_201_CREATED,
)
def register_knowledge(
    story_id: UUID, character_id: UUID, payload: CharacterKnowledgeCreate, use_cases: UseCases
) -> CharacterKnowledgeRead:
    return CharacterKnowledgeRead.model_validate(
        use_cases.create_knowledge(
            story_id,
            character_id,
            payload.model_dump() | {"story_id": story_id},
        )
    )


@router.get("/characters/{character_id}/knowledge", response_model=list[CharacterKnowledgeRead])
def list_knowledge(
    story_id: UUID, character_id: UUID, use_cases: UseCases
) -> list[CharacterKnowledgeRead]:
    return [
        CharacterKnowledgeRead.model_validate(item)
        for item in use_cases.list_knowledge(story_id, character_id)
    ]


@router.post(
    "/relationships", response_model=CharacterRelationshipRead, status_code=status.HTTP_201_CREATED
)
def create_relationship(
    story_id: UUID, payload: CharacterRelationshipCreate, use_cases: UseCases
) -> CharacterRelationshipRead:
    return CharacterRelationshipRead.model_validate(
        use_cases.create_relationship(story_id, payload.model_dump())
    )


@router.get("/relationships", response_model=list[CharacterRelationshipRead])
def list_relationships(story_id: UUID, use_cases: UseCases) -> list[CharacterRelationshipRead]:
    return [
        CharacterRelationshipRead.model_validate(item)
        for item in use_cases.list_relationships(story_id)
    ]
