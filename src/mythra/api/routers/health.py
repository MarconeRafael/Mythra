"""Verificação operacional mínima da API."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Informa que o processo HTTP está ativo."""
    return {"status": "ok"}
