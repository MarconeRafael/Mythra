"""Fixtures de integração usando um PostgreSQL descartável/configurado."""

import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mythra.api.dependencies import get_session
from mythra.infrastructure.db.session import engine as application_engine
from mythra.main import app


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Obtém uma URL explícita para PostgreSQL de teste ou pula integração."""
    url = os.getenv("MYTHRA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina MYTHRA_TEST_DATABASE_URL para executar integração PostgreSQL.")
    return url


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database(postgres_url: str) -> Generator[None, None, None]:
    """Aplica migrations reais antes dos testes e remove o esquema ao final."""
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url.replace("%", "%%"))
    command.upgrade(config, "head")
    yield
    command.downgrade(config, "base")


@pytest.fixture
def db_session(postgres_url: str) -> Generator[Session, None, None]:
    """Isola cada teste numa transação revertida após os asserts."""
    test_engine = create_engine(postgres_url)
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        test_engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Cria um cliente HTTP com a sessão PostgreSQL transacional do teste."""

    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session", autouse=True)
def dispose_application_engine() -> Generator[None, None, None]:
    """Libera o pool global da aplicação ao encerrar os testes."""
    yield
    application_engine.dispose()
