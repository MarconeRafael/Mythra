"""Interface de persistência consumida pelos casos de uso de usuários."""

from typing import Any, Protocol
from uuid import UUID


class UserStore(Protocol):
    def create(self, *, email: str, display_name: str) -> Any: ...
    def get(self, user_id: UUID) -> Any | None: ...
