"""Fronteira transacional autoritativa dos casos de uso."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol


class UnitOfWork(Protocol):
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


@contextmanager
def transaction(unit_of_work: UnitOfWork) -> Iterator[None]:
    """Confirma ao sair com sucesso e reverte tudo se qualquer escrita falhar."""
    try:
        yield
        unit_of_work.commit()
    except BaseException:
        unit_of_work.rollback()
        raise
