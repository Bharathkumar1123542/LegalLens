"""
SQLAlchemy declarative base — shared by all ORM models.
All models import Base from here, not from each other, to avoid circular imports.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
