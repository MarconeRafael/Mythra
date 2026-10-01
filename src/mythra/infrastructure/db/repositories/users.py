"""Persistência de usuários."""

from uuid import UUID

from sqlalchemy.orm import Session

from mythra.infrastructure.db.models import User


class UserRepository:
    """Operações de gravação e leitura de usuários."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, email: str, display_name: str) -> User:
        user = User(email=email, display_name=display_name)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def get(self, user_id: UUID) -> User | None:
        return self.session.get(User, user_id)
