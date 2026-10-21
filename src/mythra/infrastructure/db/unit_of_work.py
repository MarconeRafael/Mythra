"""Unidade de trabalho SQLAlchemy que detém o commit e o rollback da sessão."""

from sqlalchemy.orm import Session


class SqlAlchemyUnitOfWork:
    """Único ponto que confirma ou reverte a transação da sessão corrente."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
