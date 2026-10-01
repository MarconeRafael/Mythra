"""Aplicação HTTP da fundação persistente do Mythra."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from mythra.api.routers.characters import router as characters_router
from mythra.api.routers.health import router as health_router
from mythra.api.routers.narratives import router as narratives_router
from mythra.api.routers.stories import router as stories_router
from mythra.api.routers.users import router as users_router
from mythra.core.exceptions import ResourceNotFoundError
from mythra.core.logging import configure_logging
from mythra.domain.exceptions import DomainRuleViolation

configure_logging()
app = FastAPI(title="Mythra", version="0.1.0")
app.include_router(health_router)
app.include_router(users_router)
app.include_router(stories_router)
app.include_router(characters_router)
app.include_router(narratives_router)


@app.exception_handler(ResourceNotFoundError)
async def handle_not_found(_: Request, error: ResourceNotFoundError) -> JSONResponse:
	return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(DomainRuleViolation)
async def handle_domain_violation(_: Request, error: DomainRuleViolation) -> JSONResponse:
	return JSONResponse(status_code=422, content={"detail": str(error)})


@app.exception_handler(IntegrityError)
async def handle_integrity_error(_: Request, error: IntegrityError) -> JSONResponse:
	del error
	return JSONResponse(
		status_code=409,
		content={"detail": "Conflito com uma constraint persistente."},
	)
