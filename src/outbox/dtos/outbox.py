import typing as t
from datetime import datetime
from uuid import UUID

from src.core.schemas.base import BaseFromAttrsModel


class OutboxEventDTO(BaseFromAttrsModel):
    id: UUID
    event_type: str
    payload: dict[str, t.Any]
    created_at: datetime
    published_at: datetime | None
    attempts: int
    last_error: str | None
