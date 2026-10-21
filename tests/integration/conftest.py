"""Fixtures de integração usando um PostgreSQL descartável/configurado."""

import os
from collections.abc import Callable, Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mythra.api.dependencies import get_session
from mythra.application.use_cases import MythraUseCases
from mythra.core.config import get_settings
from mythra.infrastructure.db.models import (
    Chapter,
    Character,
    GenerationRun,
    Location,
    PlotThread,
    Scene,
    Story,
    StoryArc,
    StoryEvent,
    StoryFact,
    TimelineEvent,
    User,
)
from mythra.infrastructure.db.repositories.characters import CharacterRepository
from mythra.infrastructure.db.repositories.events import StoryEventRepository
from mythra.infrastructure.db.repositories.narratives import NarrativeRepository
from mythra.infrastructure.db.repositories.stories import StoryRepository
from mythra.infrastructure.db.repositories.transitions import StateTransitionRepository
from mythra.infrastructure.db.repositories.users import UserRepository
from mythra.infrastructure.db.session import engine as application_engine
from mythra.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from mythra.main import app


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Obtém uma URL explícita para PostgreSQL de teste ou pula integração."""
    url = os.getenv("MYTHRA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina MYTHRA_TEST_DATABASE_URL para executar integração PostgreSQL.")
    return url


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database(
    postgres_url: str, monkeypatch_session: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    """Aplica migrations reais antes dos testes e remove o esquema ao final."""
    # migrations/env.py lê a URL das settings, não de set_main_option; força o banco de teste.
    monkeypatch_session.setenv("MYTHRA_DATABASE_URL", postgres_url)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url.replace("%", "%%"))
    command.upgrade(config, "head")
    yield
    command.downgrade(config, "base")
    monkeypatch_session.undo()
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def monkeypatch_session() -> Generator[pytest.MonkeyPatch, None, None]:
    with pytest.MonkeyPatch.context() as patch:
        yield patch


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


@pytest.fixture(scope="session")
def alembic_config(postgres_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url.replace("%", "%%"))
    return config


@pytest.fixture
def use_cases(db_session: Session) -> MythraUseCases:
    """Casos de uso reais sobre a sessão transacional do teste."""
    return MythraUseCases(
        users=UserRepository(db_session),
        stories=StoryRepository(db_session),
        characters=CharacterRepository(db_session),
        narratives=NarrativeRepository(db_session),
        events=StoryEventRepository(db_session),
        unit_of_work=SqlAlchemyUnitOfWork(db_session),
        state_transitions=StateTransitionRepository(db_session),
    )


@dataclass
class World:
    """História mínima, persistida na sessão do teste, com uma entidade de cada tipo base."""

    user: User
    story: Story
    character: Character
    other_character: Character
    fact: StoryFact
    event: StoryEvent
    arc: StoryArc
    chapter: Chapter
    timeline_event: TimelineEvent
    plot_thread: PlotThread
    location: Location
    scene: Scene
    run: GenerationRun


@pytest.fixture
def make_world(db_session: Session) -> Callable[[], World]:
    """Fábrica de histórias independentes; cada chamada cria usuário e história próprios."""

    def build() -> World:
        now = datetime.now(UTC)
        user = User(email=f"{uuid4()}@example.com", display_name="Autor")
        db_session.add(user)
        db_session.flush()
        story = Story(user_id=user.id, title="História", premise="Premissa")
        db_session.add(story)
        db_session.flush()
        sid = story.id
        character = Character(story_id=sid, name="Ana", emotional_state="calma")
        other = Character(story_id=sid, name="Beto")
        fact = StoryFact(
            story_id=sid, subject="a", predicate="b", object="c", valid_from=now, source="s"
        )
        event = StoryEvent(
            story_id=sid,
            event_type="seed",
            aggregate_type="character",
            aggregate_id=uuid4(),
            payload={},
            occurred_at=now,
        )
        arc = StoryArc(story_id=sid, title="Arco", position=1, status="active")
        timeline = TimelineEvent(story_id=sid, title="Marco", occurred_at=now)
        thread = PlotThread(story_id=sid, title="Fio", status="open")
        location = Location(story_id=sid, name="Cidade")
        run = GenerationRun(
            story_id=sid, run_type="chapter", status="succeeded", base_state_version=0
        )
        db_session.add_all([character, other, fact, event, arc, timeline, thread, location, run])
        db_session.flush()
        chapter = Chapter(
            story_id=sid, arc_id=arc.id, title="Cap", position=1, status="draft"
        )
        db_session.add(chapter)
        db_session.flush()
        scene = Scene(story_id=sid, chapter_id=chapter.id, position=1, status="draft")
        db_session.add(scene)
        db_session.flush()
        return World(
            user, story, character, other, fact, event, arc, chapter, timeline, thread,
            location, scene, run,
        )  # fmt: skip

    return build
