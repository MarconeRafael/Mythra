"""Casos de uso de criação e consulta de usuários."""

from typing import Any
from uuid import UUID

from mythra.application.users.ports import UserStore
from mythra.core.exceptions import ResourceNotFoundError


class UserUseCases:
    """Coordena a criação e consulta de usuários proprietários de histórias."""

    def __init__(self, users: UserStore) -> None:
        self.users = users

    def create_user(self, email: str, display_name: str) -> Any:
        return self.users.create(email=email, display_name=display_name)

    def get_user(self, user_id: UUID) -> Any:
        user = self.users.get(user_id)
        if user is None:
            raise ResourceNotFoundError("Usuário não encontrado.")
        return user
