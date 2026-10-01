"""Rotas para timeline, threads, arcos, capítulos e eventos de história."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from mythra.api.dependencies import get_use_cases
from mythra.api.schemas import (
    ChapterCreate,
    ChapterRead,
    PlotThreadCreate,
    PlotThreadRead,
    StoryArcCreate,
    StoryArcRead,
    StoryEventCreate,
    StoryEventRead,
    TimelineEventCreate,
    TimelineEventRead,
)
from mythra.application.use_cases import MythraUseCases

router = APIRouter(prefix="/stories/{story_id}", tags=["narrative"])
UseCases = Annotated[MythraUseCases, Depends(get_use_cases)]


@router.post(
    "/timeline-events",
    response_model=TimelineEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_timeline_event(
    story_id: UUID, payload: TimelineEventCreate, use_cases: UseCases
) -> TimelineEventRead:
    return TimelineEventRead.model_validate(
        use_cases.create_timeline_event(story_id, payload.model_dump())
    )


@router.get("/timeline-events", response_model=list[TimelineEventRead])
def list_timeline_events(story_id: UUID, use_cases: UseCases) -> list[TimelineEventRead]:
    return [
        TimelineEventRead.model_validate(item)
        for item in use_cases.list_timeline_events(story_id)
    ]


@router.post("/plot-threads", response_model=PlotThreadRead, status_code=status.HTTP_201_CREATED)
def create_plot_thread(
    story_id: UUID, payload: PlotThreadCreate, use_cases: UseCases
) -> PlotThreadRead:
    result = use_cases.create_plot_thread(story_id, payload.model_dump())
    return PlotThreadRead.model_validate(result)


@router.get("/plot-threads", response_model=list[PlotThreadRead])
def list_plot_threads(story_id: UUID, use_cases: UseCases) -> list[PlotThreadRead]:
    return [PlotThreadRead.model_validate(item) for item in use_cases.list_plot_threads(story_id)]


@router.post("/arcs", response_model=StoryArcRead, status_code=status.HTTP_201_CREATED)
def create_arc(story_id: UUID, payload: StoryArcCreate, use_cases: UseCases) -> StoryArcRead:
    return StoryArcRead.model_validate(use_cases.create_arc(story_id, payload.model_dump()))


@router.get("/arcs", response_model=list[StoryArcRead])
def list_arcs(story_id: UUID, use_cases: UseCases) -> list[StoryArcRead]:
    return [StoryArcRead.model_validate(item) for item in use_cases.list_arcs(story_id)]


@router.post("/chapters", response_model=ChapterRead, status_code=status.HTTP_201_CREATED)
def create_chapter(story_id: UUID, payload: ChapterCreate, use_cases: UseCases) -> ChapterRead:
    return ChapterRead.model_validate(use_cases.create_chapter(story_id, payload.model_dump()))


@router.get("/chapters", response_model=list[ChapterRead])
def list_chapters(story_id: UUID, use_cases: UseCases) -> list[ChapterRead]:
    return [ChapterRead.model_validate(item) for item in use_cases.list_chapters(story_id)]


@router.post("/events", response_model=StoryEventRead, status_code=status.HTTP_201_CREATED)
def record_story_event(
    story_id: UUID, payload: StoryEventCreate, use_cases: UseCases
) -> StoryEventRead:
    return StoryEventRead.model_validate(
        use_cases.record_story_event(story_id, payload.model_dump())
    )


@router.get("/events", response_model=list[StoryEventRead])
def list_story_events(story_id: UUID, use_cases: UseCases) -> list[StoryEventRead]:
    return [StoryEventRead.model_validate(item) for item in use_cases.list_story_events(story_id)]
