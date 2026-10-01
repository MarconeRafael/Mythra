"""Contratos Pydantic da API, separados dos modelos relacionais."""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("O timestamp deve incluir fuso horário.")
    return value.astimezone(UTC)


UTCDateTime = Annotated[datetime, AfterValidator(_normalize_utc)]


class ReadSchema(BaseModel):
    """Configuração comum para respostas derivadas de registros persistidos."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)


class UserRead(ReadSchema):
    email: EmailStr
    display_name: str


class StoryCreate(BaseModel):
    user_id: UUID
    title: str = Field(min_length=1, max_length=300)
    premise: str = Field(min_length=1)


class StoryPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    premise: str | None = Field(default=None, min_length=1)


class StoryRead(ReadSchema):
    user_id: UUID
    title: str
    premise: str


class StoryPreferencesCreate(BaseModel):
    tone: str = Field(min_length=1)


class StoryPreferencesRead(ReadSchema):
    story_id: UUID
    tone: str


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    age: int | None = None
    personality: str | None = None
    goals: str | None = None
    fears: str | None = None
    beliefs: str | None = None
    emotional_state: str | None = None


class CharacterRead(ReadSchema):
    story_id: UUID
    name: str
    description: str | None
    age: int | None
    personality: str | None
    goals: str | None
    fears: str | None
    beliefs: str | None
    emotional_state: str | None


class StoryFactCreate(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1, max_length=200)
    object: str = Field(min_length=1)
    valid_from: UTCDateTime
    valid_to: UTCDateTime | None = None
    source: str = Field(min_length=1)


class StoryFactRead(ReadSchema):
    story_id: UUID
    subject: str
    predicate: str
    object: str
    valid_from: datetime
    valid_to: datetime | None
    source: str


class CharacterKnowledgeCreate(BaseModel):
    fact_id: UUID
    known_at: UTCDateTime
    confidence: float = Field(ge=0.0, le=1.0)
    visibility: str = Field(min_length=1)
    source_event_id: UUID


class CharacterKnowledgeRead(ReadSchema):
    story_id: UUID
    character_id: UUID
    fact_id: UUID
    known_at: datetime
    confidence: float
    visibility: str
    source_event_id: UUID


class CharacterRelationshipCreate(BaseModel):
    source_character_id: UUID
    target_character_id: UUID
    relationship_type: str = Field(min_length=1, max_length=100)
    trust: float = Field(ge=-1.0, le=1.0)
    status: str = Field(min_length=1, max_length=100)


class CharacterRelationshipRead(ReadSchema):
    story_id: UUID
    source_character_id: UUID
    target_character_id: UUID
    relationship_type: str
    trust: float
    status: str


class TimelineEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    occurred_at: UTCDateTime


class TimelineEventRead(ReadSchema):
    story_id: UUID
    title: str
    description: str | None
    occurred_at: UTCDateTime


class PlotThreadCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    status: Literal["open", "resolved", "abandoned"]


class PlotThreadRead(ReadSchema):
    story_id: UUID
    title: str
    description: str | None
    status: Literal["open", "resolved", "abandoned"]


class StoryArcCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    position: int
    status: str = Field(min_length=1, max_length=100)


class StoryArcRead(ReadSchema):
    story_id: UUID
    title: str
    description: str | None
    position: int
    status: str


class ChapterCreate(BaseModel):
    arc_id: UUID
    title: str = Field(min_length=1, max_length=300)
    position: int
    summary: str | None = None
    content: str | None = None
    status: str = Field(min_length=1, max_length=100)


class ChapterRead(ReadSchema):
    story_id: UUID
    arc_id: UUID
    title: str
    position: int
    summary: str | None
    content: str | None
    status: str


class StoryEventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=200)
    aggregate_type: str = Field(min_length=1, max_length=100)
    aggregate_id: UUID
    payload: dict[str, Any]
    occurred_at: datetime


class StoryEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    story_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    payload: dict[str, Any]
    occurred_at: datetime
    created_at: datetime
