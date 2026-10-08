"""Shared schemas: pagination, generic responses."""

from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints."""
    skip: int = 0
    limit: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    items: list[T]
    total: int
    skip: int
    limit: int
    has_more: bool


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    detail: Optional[str] = None
