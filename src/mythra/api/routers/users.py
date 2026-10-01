"""Rotas para criação e consulta de usuários."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from mythra.api.dependencies import get_use_cases
from mythra.api.schemas import UserCreate, UserRead
from mythra.application.use_cases import MythraUseCases

router = APIRouter(prefix="/users", tags=["users"])
UseCases = Annotated[MythraUseCases, Depends(get_use_cases)]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, use_cases: UseCases) -> UserRead:
    return UserRead.model_validate(use_cases.create_user(str(payload.email), payload.display_name))


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, use_cases: UseCases) -> UserRead:
    return UserRead.model_validate(use_cases.get_user(user_id))
