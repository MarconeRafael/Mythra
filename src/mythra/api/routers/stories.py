"""Rotas para histórias e preferências."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from mythra.api.dependencies import get_use_cases
from mythra.api.schemas import (
    StoryCreate,
    StoryPatch,
    StoryPreferencesCreate,
    StoryPreferencesRead,
    StoryRead,
)
from mythra.application.use_cases import MythraUseCases

router = APIRouter(prefix="/stories", tags=["stories"])
UseCases = Annotated[MythraUseCases, Depends(get_use_cases)]


@router.post("", response_model=StoryRead, status_code=status.HTTP_201_CREATED)
def create_story(payload: StoryCreate, use_cases: UseCases) -> StoryRead:
    return StoryRead.model_validate(
        use_cases.create_story(payload.user_id, payload.title, payload.premise)
    )


@router.get("/{story_id}", response_model=StoryRead)
def get_story(story_id: UUID, use_cases: UseCases) -> StoryRead:
    return StoryRead.model_validate(use_cases.get_story(story_id))


@router.patch("/{story_id}", response_model=StoryRead)
def update_story(story_id: UUID, payload: StoryPatch, use_cases: UseCases) -> StoryRead:
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Campos obrigatórios não podem ser nulos.")
    return StoryRead.model_validate(use_cases.update_story(story_id, changes))


@router.post(
    "/{story_id}/preferences",
    response_model=StoryPreferencesRead,
    status_code=status.HTTP_201_CREATED,
)
def configure_preferences(
    story_id: UUID, payload: StoryPreferencesCreate, use_cases: UseCases
) -> StoryPreferencesRead:
    return StoryPreferencesRead.model_validate(use_cases.create_preferences(story_id, payload.tone))


@router.get("/{story_id}/preferences", response_model=StoryPreferencesRead)
def get_preferences(story_id: UUID, use_cases: UseCases) -> StoryPreferencesRead:
    return StoryPreferencesRead.model_validate(use_cases.get_preferences(story_id))
