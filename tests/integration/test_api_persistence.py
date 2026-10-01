"""Fluxo integrado da API sobre migrations e persistência PostgreSQL reais."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mythra.infrastructure.db.models import (
    Chapter,
    Character,
    CharacterKnowledge,
    CharacterRelationship,
    Story,
    StoryArc,
    StoryEvent,
    StoryFact,
    User,
)


def _story_with_character(db_session: Session, suffix: str) -> tuple[Story, Character]:
    user = User(email=f"{uuid4()}@example.com", display_name=suffix)
    db_session.add(user)
    db_session.flush()
    story = Story(user_id=user.id, title=suffix, premise=suffix)
    db_session.add(story)
    db_session.flush()
    character = Character(story_id=story.id, name=suffix)
    db_session.add(character)
    db_session.flush()
    return story, character


def _fact_event(db_session: Session, story: Story) -> tuple[StoryFact, StoryEvent]:
    now = datetime.now(UTC)
    fact = StoryFact(
        story_id=story.id,
        subject="subject",
        predicate="knows",
        object="object",
        valid_from=now,
        source="test",
    )
    event = StoryEvent(
        story_id=story.id,
        event_type="knowledge_registered",
        aggregate_type="character",
        aggregate_id=uuid4(),
        payload={},
        occurred_at=now,
    )
    db_session.add_all([fact, event])
    db_session.flush()
    return fact, event


def test_phase_one_entity_creation_flow(client: TestClient) -> None:
    user = client.post(
        "/users", json={"email": f"{uuid4()}@example.com", "display_name": "Ariadne"}
    )
    assert user.status_code == 201
    user_id = user.json()["id"]

    story = client.post(
        "/stories", json={"user_id": user_id, "title": "Labyrinth", "premise": "A lost city."}
    )
    assert story.status_code == 201
    story_id = story.json()["id"]

    preferences = client.post(
        f"/stories/{story_id}/preferences", json={"tone": "mythic"}
    )
    assert preferences.status_code == 201
    first_character = client.post(
        f"/stories/{story_id}/characters", json={"name": "Ariadne", "age": 24}
    )
    second_character = client.post(
        f"/stories/{story_id}/characters", json={"name": "Theseus"}
    )
    assert first_character.status_code == second_character.status_code == 201

    event = client.post(
        f"/stories/{story_id}/events",
        json={
            "event_type": "character_created",
            "aggregate_type": "character",
            "aggregate_id": first_character.json()["id"],
            "payload": {"name": "Ariadne"},
            "occurred_at": datetime.now(UTC).isoformat(),
        },
    )
    assert event.status_code == 201

    fact = client.post(
        f"/stories/{story_id}/facts",
        json={
            "subject": "Ariadne",
            "predicate": "gave_thread_to",
            "object": "Theseus",
            "valid_from": datetime.now(UTC).isoformat(),
            "source": "witnessed",
        },
    )
    assert fact.status_code == 201
    knowledge = client.post(
        f"/stories/{story_id}/characters/{first_character.json()['id']}/knowledge",
        json={
            "fact_id": fact.json()["id"],
            "known_at": datetime.now(UTC).isoformat(),
            "confidence": 0.8,
            "visibility": "known",
            "source_event_id": event.json()["id"],
        },
    )
    assert knowledge.status_code == 201

    relationship = client.post(
        f"/stories/{story_id}/relationships",
        json={
            "source_character_id": first_character.json()["id"],
            "target_character_id": second_character.json()["id"],
            "relationship_type": "ally",
            "trust": 0.5,
            "status": "active",
        },
    )
    assert relationship.status_code == 201

    assert client.post(
        f"/stories/{story_id}/timeline-events",
        json={"title": "Departure", "occurred_at": datetime.now(UTC).isoformat()},
    ).status_code == 201
    assert client.post(
        f"/stories/{story_id}/plot-threads",
        json={"title": "The return", "status": "open"},
    ).status_code == 201
    arc = client.post(
        f"/stories/{story_id}/arcs", json={"title": "Exile", "position": 1, "status": "active"}
    )
    assert arc.status_code == 201
    chapter = client.post(
        f"/stories/{story_id}/chapters",
        json={"arc_id": arc.json()["id"], "title": "The road", "position": 1, "status": "draft"},
    )
    assert chapter.status_code == 201
    assert client.get(f"/stories/{story_id}/events").json()[0]["event_type"] == "character_created"


def test_database_check_constraint_rejects_invalid_trust(db_session: Session) -> None:
    user = User(email=f"{uuid4()}@example.com", display_name="Test")
    db_session.add(user)
    db_session.flush()
    story = Story(user_id=user.id, title="Test", premise="Test")
    db_session.add(story)
    db_session.flush()
    source = Character(story_id=story.id, name="Source")
    target = Character(story_id=story.id, name="Target")
    db_session.add_all([source, target])
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO character_relationships "
                "(id, created_at, updated_at, story_id, source_character_id, target_character_id, "
                "relationship_type, trust, status) VALUES "
                "(:id, now(), now(), :story, :source, :target, 'rival', 2.0, 'hostile')"
            ),
            {
                "id": uuid4(),
                "story": story.id,
                "source": source.id,
                "target": target.id,
            },
        )


def test_database_check_constraint_rejects_invalid_confidence(db_session: Session) -> None:
    story, character = _story_with_character(db_session, "confidence")
    fact, event = _fact_event(db_session, story)
    db_session.add(
        CharacterKnowledge(
            story_id=story.id,
            character_id=character.id,
            fact_id=fact.id,
            known_at=datetime.now(UTC),
            confidence=1.5,
            visibility="known",
            source_event_id=event.id,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_database_rejects_duplicate_directed_relationship(db_session: Session) -> None:
    story, source = _story_with_character(db_session, "relation")
    target = Character(story_id=story.id, name="target")
    db_session.add(target)
    db_session.flush()
    fields = {
        "story_id": story.id,
        "source_character_id": source.id,
        "target_character_id": target.id,
        "relationship_type": "ally",
        "trust": 0.4,
        "status": "active",
    }
    db_session.add_all([CharacterRelationship(**fields), CharacterRelationship(**fields)])
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_database_rejects_relationship_across_stories(db_session: Session) -> None:
    story, source = _story_with_character(db_session, "source-story")
    _, target = _story_with_character(db_session, "target-story")
    db_session.add(
        CharacterRelationship(
            story_id=story.id,
            source_character_id=source.id,
            target_character_id=target.id,
            relationship_type="ally",
            trust=0.4,
            status="active",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_database_rejects_chapter_for_arc_from_another_story(db_session: Session) -> None:
    story, _ = _story_with_character(db_session, "chapter-story")
    other_story, _ = _story_with_character(db_session, "arc-story")
    arc = StoryArc(story_id=other_story.id, title="Arc", position=1, status="active")
    db_session.add(arc)
    db_session.flush()
    db_session.add(
        Chapter(story_id=story.id, arc_id=arc.id, title="Chapter", position=1, status="draft")
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_database_rejects_knowledge_that_crosses_story_boundaries(db_session: Session) -> None:
    story, character = _story_with_character(db_session, "knowledge-story")
    other_story, _ = _story_with_character(db_session, "fact-story")
    fact, _ = _fact_event(db_session, other_story)
    source_event = StoryEvent(
        story_id=story.id,
        event_type="knowledge_registered",
        aggregate_type="character",
        aggregate_id=character.id,
        payload={},
        occurred_at=datetime.now(UTC),
    )
    db_session.add(source_event)
    db_session.flush()
    db_session.add(
        CharacterKnowledge(
            story_id=story.id,
            character_id=character.id,
            fact_id=fact.id,
            known_at=datetime.now(UTC),
            confidence=0.7,
            visibility="known",
            source_event_id=source_event.id,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_database_rejects_duplicate_character_fact_knowledge(db_session: Session) -> None:
    story, character = _story_with_character(db_session, "duplicate-knowledge")
    fact, event = _fact_event(db_session, story)
    values = {
        "story_id": story.id,
        "character_id": character.id,
        "fact_id": fact.id,
        "known_at": datetime.now(UTC),
        "confidence": 0.6,
        "visibility": "suspected",
        "source_event_id": event.id,
    }
    db_session.add_all([CharacterKnowledge(**values), CharacterKnowledge(**values)])
    with pytest.raises(IntegrityError):
        db_session.flush()
