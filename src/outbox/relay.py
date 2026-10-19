import asyncio
import contextlib
import typing as t

from src.core.settings.log import get_logger
from src.outbox.logic.use_cases.publish_outbox_batch import PublishOutboxBatchUseCase

if t.TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.outbox.publisher import EventPublisher

logger = get_logger(__name__)


class OutboxRelay:
    """
    Фоновый цикл переноса событий из outbox в брокер.

    Пока события есть, пачки публикуются без пауз; когда outbox пуст (или публикация сломалась),
    relay ждёт poll_interval перед следующей выборкой.
    """

    def __init__(
        self,
        session_factory: 'async_sessionmaker[AsyncSession]',
        publisher: 'EventPublisher',
        batch_size: int,
        poll_interval: float,
    ) -> None:
        self.session_factory = session_factory
        self.publisher = publisher
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self._stopping = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name='outbox-relay')
        logger.info('Outbox relay запущен', batch_size=self.batch_size, poll_interval=self.poll_interval)

    async def stop(self) -> None:
        """Мягкая остановка: текущая пачка дописывается до конца"""
        self._stopping.set()
        if self._task is not None:
            await self._task
            self._task = None
        logger.info('Outbox relay остановлен')

    async def publish_batch(self) -> int:
        async with self.session_factory() as session:
            use_case = PublishOutboxBatchUseCase(session=session, publisher=self.publisher, batch_size=self.batch_size)
            return await use_case.execute()

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                published = await self.publish_batch()
            except Exception:
                logger.exception('Ошибка outbox relay')
                published = 0

            if published < self.batch_size:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stopping.wait(), timeout=self.poll_interval)
