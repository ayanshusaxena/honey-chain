"""Authoritative SQLAlchemy declarative base for all future ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class inherited by future Honey Chain ORM models."""
