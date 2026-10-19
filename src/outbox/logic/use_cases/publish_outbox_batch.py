import typing as t

from src.core.settings.log import get_logger
from src.core.use_cases.base import BaseSessionAsyncUseCase
from src.outbox.repositories import OutboxRepository

if t.TYPE_CHECKING:
    from src.outbox.publisher import EventPublisher

logger = get_logger(__name__)


class PublishOutboxBatchUseCase(BaseSessionAsyncUseCase):
    """
    Публикация пачки неопубликованных событий outbox.

    Строки блокируются (FOR UPDATE SKIP LOCKED) на всё время публикации, отметка published_at
    фиксируется после подтверждения брокера. При сбое между публикацией и commit событие будет
    отправлено повторно — гарантия at-least-once, дубли поглощает идемпотентный consumer.
    При ошибке публикации пачка прерывается: брокер скорее всего недоступен, и порядок событий сохраняется.
    """

    def __init__(
        self,
        publisher: 'EventPublisher',
        batch_size: int,
        outbox_repo: type[OutboxRepository] = OutboxRepository,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.publisher = publisher
        self.batch_size = batch_size
        self.outbox_repo = outbox_repo(self.session)

    async def execute(self) -> int:
        """Возвращает количество опубликованных событий"""
        events = await self.outbox_repo.lock_unpublished(limit=self.batch_size)
        published_ids = []
        for event in events:
            try:
                await self.publisher.publish(event)
            except Exception as err:
                logger.exception('Ошибка публикации события outbox', event_id=str(event.id))
                await self.outbox_repo.mark_failed(event.id, error=repr(err))
                break
            published_ids.append(event.id)

        if published_ids:
            await self.outbox_repo.mark_published(published_ids)
        await self.session.commit()

        if published_ids:
            logger.info('События outbox опубликованы', count=len(published_ids))
        return len(published_ids)
