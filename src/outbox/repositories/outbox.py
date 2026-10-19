import typing as t
from uuid import UUID

from sqlalchemy import func, select, update

from src.outbox.dtos import OutboxEventDTO
from src.outbox.models import OutboxEvent

if t.TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


class OutboxRepository:
    def __init__(self, session: 'AsyncSession') -> None:
        self.session = session

    def add(self, event_id: UUID, event_type: str, payload: dict[str, t.Any]) -> None:
        """Добавление события в текущую транзакцию"""
        self.session.add(OutboxEvent(id=event_id, event_type=event_type, payload=payload))

    async def lock_unpublished(self, limit: int) -> list[OutboxEventDTO]:
        """
        Выборка неопубликованных событий с блокировкой строк до конца транзакции.

        SKIP LOCKED позволяет запускать несколько relay параллельно: каждый получает
        свою пачку событий, и одно событие не уходит в брокер дважды одновременно.
        """
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        events = await self.session.scalars(stmt)
        return [OutboxEventDTO.model_validate(event) for event in events]

    async def mark_published(self, event_ids: 'Sequence[UUID]') -> None:
        """Отметка событий как опубликованных"""
        stmt = update(OutboxEvent).where(OutboxEvent.id.in_(event_ids)).values(published_at=func.now())
        await self.session.execute(stmt)

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        """Фиксация неудачной попытки публикации"""
        stmt = (
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(attempts=OutboxEvent.attempts + 1, last_error=error)
        )
        await self.session.execute(stmt)
