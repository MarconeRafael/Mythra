"""Testes unitários para invariantes puros do domínio."""

from uuid import uuid4

import pytest

from mythra.domain.characters.rules import CharacterKnowledgeState, RelationshipState
from mythra.domain.exceptions import DomainRuleViolation
from mythra.domain.narratives.rules import ChapterPlacement, StoryArcState
from mythra.domain.stories.rules import StoryState


def test_relationship_accepts_trust_boundaries() -> None:
    story_id = uuid4()
    source_id, target_id = uuid4(), uuid4()

    assert RelationshipState(story_id, source_id, target_id, "ally", -1.0, "hostile")
    assert RelationshipState(story_id, source_id, target_id, "ally", 1.0, "trusted")


@pytest.mark.parametrize("trust", [-1.01, 1.01])
def test_relationship_rejects_trust_outside_range(trust: float) -> None:
    with pytest.raises(DomainRuleViolation, match="trust"):
        RelationshipState(uuid4(), uuid4(), uuid4(), "rival", trust, "active")


def test_relationship_rejects_self_reference() -> None:
    character_id = uuid4()
    with pytest.raises(DomainRuleViolation, match="consigo mesma"):
        RelationshipState(uuid4(), character_id, character_id, "self", 0.0, "active")


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_knowledge_accepts_confidence_boundaries(confidence: float) -> None:
    assert CharacterKnowledgeState(uuid4(), uuid4(), confidence, "private")


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_knowledge_rejects_confidence_outside_range(confidence: float) -> None:
    with pytest.raises(DomainRuleViolation, match="confidence"):
        CharacterKnowledgeState(uuid4(), uuid4(), confidence, "private")


def test_chapter_requires_arc_from_same_story() -> None:
    with pytest.raises(DomainRuleViolation, match="mesma história"):
        ChapterPlacement(uuid4(), uuid4(), uuid4(), 1)


def test_chapter_accepts_arc_from_same_story() -> None:
    story_id = uuid4()
    assert ChapterPlacement(story_id, story_id, uuid4(), 1)


def test_story_requires_a_title_and_premise() -> None:
    with pytest.raises(DomainRuleViolation, match="obrigatórios"):
        StoryState(uuid4(), " ", "Premissa")


def test_story_arc_requires_a_title_and_status() -> None:
    with pytest.raises(DomainRuleViolation, match="obrigatórios"):
        StoryArcState(uuid4(), "Arco", 0, " ")
