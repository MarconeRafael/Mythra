"""Base declarativa compartilhada pelos modelos SQLAlchemy."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    """Raiz dos metadados relacionais da aplicação."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
