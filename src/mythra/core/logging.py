"""Inicialização simples do logging da aplicação."""

import logging

from mythra.core.config import get_settings


def configure_logging() -> None:
    """Configura o nível global de logging a partir do ambiente."""
    logging.basicConfig(level=getattr(logging, get_settings().log_level.upper(), logging.INFO))
