"""Dependências HTTP para sessão e casos de uso."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from mythra.application.use_cases import MythraUseCases
from mythra.infrastructure.db.repositories.characters import CharacterRepository
from mythra.infrastructure.db.repositories.events import StoryEventRepository
from mythra.infrastructure.db.repositories.narratives import NarrativeRepository
from mythra.infrastructure.db.repositories.stories import StoryRepository
from mythra.infrastructure.db.repositories.users import UserRepository
from mythra.infrastructure.db.session import get_session

__all__ = ["get_session", "get_use_cases"]


def get_use_cases(
    session: Annotated[Session, Depends(get_session)],
) -> MythraUseCases:
    """Monta os casos de uso com repositories associados à sessão atual."""
    return MythraUseCases(
        users=UserRepository(session),
        stories=StoryRepository(session),
        characters=CharacterRepository(session),
        narratives=NarrativeRepository(session),
        events=StoryEventRepository(session),
    )