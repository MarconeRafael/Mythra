"""Transições de estado canônico: contrato de eventos, no-op, rollback e isolamento."""

from datetime import UTC, datetime
from typing import Any, NamedTuple
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from mythra.application.state.snapshot import StoryStateSnapshot
from mythra.application.use_cases import MythraUseCases
from mythra.infrastructure.db.repositories.characters import CharacterRepository
from mythra.infrastructure.db.repositories.events import StoryEventRepository
from mythra.infrastructure.db.repositories.narratives import NarrativeRepository
from mythra.infrastructure.db.repositories.stories import StoryRepository
from mythra.infrastructure.db.repositories.users import UserRepository
from mythra.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 2, 1, tzinfo=UTC)


class Scenario(NamedTuple):
    story_id: str
    character_id: str
    other_character_id: str
    relationship_id: str
    fact_id: str
    timeline_event_id: str
    plot_thread_id: str
    arc_id: str
    chapter_id: str


def _post(client: TestClient, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=body)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def _build_story(client: TestClient) -> Scenario:
    user = _post(client, "/users", {"email": f"{uuid4()}@example.com", "display_name": "Ana"})
    story = _post(
        client, "/stories", {"user_id": user["id"], "title": "Labyrinth", "premise": "Lost."}
    )
    base = f"/stories/{story['id']}"
    ariadne = _post(client, f"{base}/characters", {"name": "Ariadne", "age": 24})
    theseus = _post(client, f"{base}/characters", {"name": "Theseus"})
    relationship = _post(
        client,
        f"{base}/relationships",
        {
            "source_character_id": ariadne["id"],
            "target_character_id": theseus["id"],
            "relationship_type": "ally",
            "trust": 0.5,
            "status": "active",
        },
    )
    fact = _post(
        client,
        f"{base}/facts",
        {
            "subject": "Ariadne",
            "predicate": "gave_thread_to",
            "object": "Theseus",
            "valid_from": T0.isoformat(),
            "source": "witnessed",
        },
    )
    source_event = _post(
        client,
        f"{base}/events",
        {
            "event_type": "scene_witnessed",
            "aggregate_type": "character",
            "aggregate_id": ariadne["id"],
            "payload": {},
            "occurred_at": T0.isoformat(),
        },
    )
    _post(
        client,
        f"{base}/characters/{ariadne['id']}/knowledge",
        {
            "fact_id": fact["id"],
            "known_at": T0.isoformat(),
            "confidence": 0.8,
            "visibility": "known",
            "source_event_id": source_event["id"],
        },
    )
    timeline = _post(
        client, f"{base}/timeline-events", {"title": "Departure", "occurred_at": T0.isoformat()}
    )
    thread = _post(client, f"{base}/plot-threads", {"title": "Return", "status": "open"})
    arc = _post(client, f"{base}/arcs", {"title": "Exile", "position": 1, "status": "active"})
    chapter = _post(
        client,
        f"{base}/chapters",
        {"arc_id": arc["id"], "title": "Road", "position": 1, "status": "draft"},
    )
    return Scenario(
        story["id"],
        ariadne["id"],
        theseus["id"],
        relationship["id"],
        fact["id"],
        timeline["id"],
        thread["id"],
        arc["id"],
        chapter["id"],
    )


@pytest.fixture
def scenario(client: TestClient) -> Scenario:
    return _build_story(client)


def _instant(value: Any) -> Any:
    """Responses serialize timestamps in the session timezone; compare the instant."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).astimezone(UTC)
        except ValueError:
            return value
    return value


def _events(client: TestClient, story_id: str, event_type: str) -> list[dict[str, Any]]:
    events = client.get(f"/stories/{story_id}/events").json()
    return [event for event in events if event["event_type"] == event_type]


type _Case = tuple[str, dict[str, Any], str, str, str, dict[str, Any]]


def _transition_cases(s: Scenario) -> list[_Case]:
    base = f"/stories/{s.story_id}"
    return [
        (
            f"{base}/characters/{s.character_id}",
            {"emotional_state": "afraid", "age": 25},
            "character_state_updated",
            "character",
            s.character_id,
            {
                "emotional_state": {"before": None, "after": "afraid"},
                "age": {"before": 24, "after": 25},
            },
        ),
        (
            f"{base}/relationships/{s.relationship_id}",
            {"trust": -0.25, "status": "broken"},
            "relationship_updated",
            "relationship",
            s.relationship_id,
            {
                "trust": {"before": 0.5, "after": -0.25},
                "status": {"before": "active", "after": "broken"},
            },
        ),
        (
            f"{base}/characters/{s.character_id}/knowledge/{s.fact_id}",
            {"confidence": 0.3, "visibility": "doubted", "known_at": T1.isoformat()},
            "character_knowledge_updated",
            "character_knowledge",
            "",
            {
                "confidence": {"before": 0.8, "after": 0.3},
                "visibility": {"before": "known", "after": "doubted"},
                "known_at": {"before": T0.isoformat(), "after": T1.isoformat()},
            },
        ),
        (
            f"{base}/facts/{s.fact_id}",
            {"object": "the minotaur", "valid_to": T1.isoformat()},
            "canonical_fact_updated",
            "story_fact",
            s.fact_id,
            {
                "object": {"before": "Theseus", "after": "the minotaur"},
                "valid_to": {"before": None, "after": T1.isoformat()},
            },
        ),
        (
            f"{base}/timeline-events/{s.timeline_event_id}",
            {"occurred_at": T1.isoformat()},
            "timeline_event_updated",
            "timeline_event",
            s.timeline_event_id,
            {"occurred_at": {"before": T0.isoformat(), "after": T1.isoformat()}},
        ),
        (
            f"{base}/plot-threads/{s.plot_thread_id}",
            {"status": "resolved"},
            "plot_thread_updated",
            "plot_thread",
            s.plot_thread_id,
            {"status": {"before": "open", "after": "resolved"}},
        ),
        (
            f"{base}/arcs/{s.arc_id}",
            {"status": "closed", "description": "Over."},
            "story_arc_updated",
            "story_arc",
            s.arc_id,
            {
                "status": {"before": "active", "after": "closed"},
                "description": {"before": None, "after": "Over."},
            },
        ),
        (
            f"{base}/chapters/{s.chapter_id}",
            {"status": "published", "content": "Text."},
            "chapter_updated",
            "chapter",
            s.chapter_id,
            {
                "status": {"before": "draft", "after": "published"},
                "content": {"before": None, "after": "Text."},
            },
        ),
    ]


@pytest.mark.parametrize("index", range(8))
def test_each_effective_transition_persists_exactly_one_typed_event(
    client: TestClient, scenario: Scenario, index: int
) -> None:
    path, body, event_type, aggregate_type, aggregate_id, changes = _transition_cases(scenario)[
        index
    ]
    before_total = len(client.get(f"/stories/{scenario.story_id}/events").json())

    response = client.patch(path, json=body)

    assert response.status_code == 200, response.text
    for field, change in changes.items():
        assert _instant(response.json()[field]) == _instant(change["after"])
    events = _events(client, scenario.story_id, event_type)
    assert len(events) == 1
    assert len(client.get(f"/stories/{scenario.story_id}/events").json()) == before_total + 1
    event = events[0]
    assert event["payload"] == {"changes": changes}
    assert event["aggregate_type"] == aggregate_type
    if aggregate_type == "character_knowledge":
        aggregate_id = client.get(
            f"/stories/{scenario.story_id}/characters/{scenario.character_id}/knowledge"
        ).json()[0]["id"]
    assert event["aggregate_id"] == aggregate_id
    assert event["story_id"] == scenario.story_id
    assert _instant(event["occurred_at"]).tzinfo is not None


@pytest.mark.parametrize("index", range(8))
def test_reapplying_an_effective_patch_is_a_noop_for_every_transition(
    client: TestClient, scenario: Scenario, index: int
) -> None:
    path, body, *_ = _transition_cases(scenario)[index]
    first = client.patch(path, json=body)
    assert first.status_code == 200
    total = len(client.get(f"/stories/{scenario.story_id}/events").json())

    second = client.patch(path, json=body)

    assert second.status_code == 200
    assert second.json() == first.json()
    assert len(client.get(f"/stories/{scenario.story_id}/events").json()) == total


@pytest.mark.parametrize("index", range(8))
def test_every_transition_is_story_scoped(
    client: TestClient, scenario: Scenario, index: int
) -> None:
    other = _build_story(client)
    path, body, *_ = _transition_cases(scenario)[index]
    foreign_path = path.replace(scenario.story_id, other.story_id, 1)
    stories = (scenario.story_id, other.story_id)
    totals = [len(client.get(f"/stories/{s}/events").json()) for s in stories]

    response = client.patch(foreign_path, json=body)

    assert response.status_code == 404
    assert totals == [len(client.get(f"/stories/{s}/events").json()) for s in stories]


@pytest.mark.parametrize("index", range(8))
def test_every_transition_rejects_ownership_and_system_fields(
    client: TestClient, scenario: Scenario, index: int
) -> None:
    path, *_ = _transition_cases(scenario)[index]
    total = len(client.get(f"/stories/{scenario.story_id}/events").json())
    forbidden_bodies = [
        {"story_id": str(uuid4())},
        {"id": str(uuid4())},
        {"created_at": T0.isoformat()},
    ]

    for forbidden in forbidden_bodies:
        assert client.patch(path, json=forbidden).status_code == 422
    assert len(client.get(f"/stories/{scenario.story_id}/events").json()) == total


def test_fact_creation_attaches_canonical_fact_created_event(
    client: TestClient, scenario: Scenario
) -> None:
    created = _post(
        client,
        f"/stories/{scenario.story_id}/facts",
        {
            "subject": "Minos",
            "predicate": "rules",
            "object": "Crete",
            "valid_from": T0.isoformat(),
            "source": "chronicle",
        },
    )

    events = [
        event
        for event in _events(client, scenario.story_id, "canonical_fact_created")
        if event["aggregate_id"] == created["id"]
    ]
    assert len(events) == 1
    assert events[0]["payload"] == {
        "changes": {
            "subject": {"before": None, "after": "Minos"},
            "predicate": {"before": None, "after": "rules"},
            "object": {"before": None, "after": "Crete"},
            "valid_from": {"before": None, "after": T0.isoformat()},
            "source": {"before": None, "after": "chronicle"},
        }
    }


def test_payload_contains_only_fields_that_actually_changed(
    client: TestClient, scenario: Scenario
) -> None:
    path = f"/stories/{scenario.story_id}/characters/{scenario.character_id}"

    response = client.patch(path, json={"name": "Ariadne", "age": 30})

    assert response.status_code == 200
    (event,) = _events(client, scenario.story_id, "character_state_updated")
    assert event["payload"] == {"changes": {"age": {"before": 24, "after": 30}}}


@pytest.mark.parametrize("body", [{}, {"name": "Ariadne", "age": 24}])
def test_idempotent_patch_returns_resource_without_mutation_or_event(
    client: TestClient, scenario: Scenario, body: dict[str, Any]
) -> None:
    path = f"/stories/{scenario.story_id}/characters/{scenario.character_id}"
    current = client.get(f"/stories/{scenario.story_id}/characters").json()[0]
    total = len(client.get(f"/stories/{scenario.story_id}/events").json())

    response = client.patch(path, json=body)

    assert response.status_code == 200
    assert response.json() == current
    assert len(client.get(f"/stories/{scenario.story_id}/events").json()) == total


@pytest.mark.parametrize(
    ("suffix", "body"),
    [
        ("relationships/{relationship_id}", {"trust": 1.5}),
        ("relationships/{relationship_id}", {"status": None}),
        ("characters/{character_id}", {"name": None}),
        ("characters/{character_id}", {"story_id": str(uuid4())}),
        ("facts/{fact_id}", {"valid_from": "2026-01-01T00:00:00"}),
        ("plot-threads/{plot_thread_id}", {"status": "paused"}),
        ("characters/{character_id}/knowledge/{fact_id}", {"confidence": -0.1}),
        ("characters/{character_id}/knowledge/{fact_id}", {"visibility": None}),
        ("facts/{fact_id}", {"subject": None}),
        ("timeline-events/{timeline_event_id}", {"occurred_at": None}),
        ("timeline-events/{timeline_event_id}", {"occurred_at": "2026-01-01T00:00:00"}),
        ("arcs/{arc_id}", {"position": None}),
        ("chapters/{chapter_id}", {"status": None}),
    ],
)
def test_rejected_transition_changes_nothing_and_writes_no_event(
    client: TestClient, scenario: Scenario, suffix: str, body: dict[str, Any]
) -> None:
    total = len(client.get(f"/stories/{scenario.story_id}/events").json())
    snapshot = client.get(f"/stories/{scenario.story_id}/relationships").json()

    response = client.patch(
        f"/stories/{scenario.story_id}/{suffix.format(**scenario._asdict())}", json=body
    )

    assert response.status_code == 422
    assert len(client.get(f"/stories/{scenario.story_id}/events").json()) == total
    assert client.get(f"/stories/{scenario.story_id}/relationships").json() == snapshot


def test_failed_event_insertion_rolls_back_the_state_change(
    client: TestClient, scenario: Scenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_append(*_: object, **__: object) -> None:
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr(StoryEventRepository, "append", failing_append)
    path = f"/stories/{scenario.story_id}/relationships/{scenario.relationship_id}"

    with pytest.raises(RuntimeError):
        client.patch(path, json={"trust": 0.9})
    monkeypatch.undo()

    relationship = client.get(f"/stories/{scenario.story_id}/relationships").json()[0]
    assert relationship["trust"] == 0.5
    assert _events(client, scenario.story_id, "relationship_updated") == []


@pytest.mark.parametrize("index", range(8))
def test_event_failure_rolls_back_every_transition(
    client: TestClient, scenario: Scenario, monkeypatch: pytest.MonkeyPatch, index: int
) -> None:
    path, body, event_type, *_ = _transition_cases(scenario)[index]

    def failing_append(*_: object, **__: object) -> None:
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr(StoryEventRepository, "append", failing_append)
    with pytest.raises(RuntimeError):
        client.patch(path, json=body)
    monkeypatch.undo()

    # A leaked mutation would make this retry a no-op and emit no event.
    assert client.patch(path, json=body).status_code == 200
    assert len(_events(client, scenario.story_id, event_type)) == 1


def test_failed_fact_event_insertion_rolls_back_fact_creation(
    client: TestClient, scenario: Scenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_append(*_: object, **__: object) -> None:
        raise RuntimeError("event store unavailable")

    facts_before = client.get(f"/stories/{scenario.story_id}/facts").json()
    monkeypatch.setattr(StoryEventRepository, "append", failing_append)

    with pytest.raises(RuntimeError):
        client.post(
            f"/stories/{scenario.story_id}/facts",
            json={
                "subject": "x",
                "predicate": "y",
                "object": "z",
                "valid_from": T0.isoformat(),
                "source": "s",
            },
        )
    monkeypatch.undo()

    assert client.get(f"/stories/{scenario.story_id}/facts").json() == facts_before


def test_transitions_are_isolated_between_stories(client: TestClient, scenario: Scenario) -> None:
    other = _build_story(client)
    base = f"/stories/{scenario.story_id}"

    foreign = client.patch(
        f"{base}/characters/{other.character_id}", json={"emotional_state": "angry"}
    )
    foreign_knowledge = client.patch(
        f"{base}/characters/{scenario.character_id}/knowledge/{other.fact_id}",
        json={"confidence": 0.1},
    )

    assert foreign.status_code == 404
    assert foreign_knowledge.status_code == 404
    assert _events(client, other.story_id, "character_state_updated") == []
    assert client.get(f"/stories/{other.story_id}/characters").json()[0]["emotional_state"] is None


def _use_cases(session: Session) -> MythraUseCases:
    return MythraUseCases(
        users=UserRepository(session),
        stories=StoryRepository(session),
        characters=CharacterRepository(session),
        narratives=NarrativeRepository(session),
        events=StoryEventRepository(session),
        unit_of_work=SqlAlchemyUnitOfWork(session),
    )


def test_story_state_snapshot_is_typed_current_state_without_history(
    client: TestClient, scenario: Scenario, db_session: Session
) -> None:
    client.patch(
        f"/stories/{scenario.story_id}/relationships/{scenario.relationship_id}",
        json={"trust": 0.1},
    )
    other = _build_story(client)
    use_cases = _use_cases(db_session)

    state = use_cases.get_story_state(UUID(scenario.story_id))

    assert isinstance(state, StoryStateSnapshot)
    assert str(state.story.id) == scenario.story_id
    assert state.preferences is None
    assert {c.name for c in state.characters} == {"Ariadne", "Theseus"}
    assert [r.trust for r in state.relationships] == [0.1]
    assert len(state.facts) == 1
    assert len(state.knowledge) == 1
    assert state.knowledge[0].confidence == 0.8
    assert (len(state.timeline_events), len(state.plot_threads)) == (1, 1)
    assert (len(state.arcs), len(state.chapters)) == (1, 1)
    assert not hasattr(state, "events")
    assert str(other.character_id) not in {str(c.id) for c in state.characters}
    with pytest.raises(AttributeError):
        state.story.title = "changed"  # type: ignore[misc]
