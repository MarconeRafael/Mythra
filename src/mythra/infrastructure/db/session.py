"""Criação do engine e das sessões PostgreSQL."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mythra.core.config import get_settings

engine = create_engine(get_settings().database_url.get_secret_value(), pool_pre_ping=True)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """Fornece uma sessão por requisição e garante seu fechamento."""
    with SessionFactory() as session:
        yield session
