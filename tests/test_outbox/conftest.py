import asyncio

import pytest
from sqlalchemy import select

from src.outbox.models import OutboxEvent


class FakePublisher:
    """Публикатор в памяти; может падать на заданных событиях и имитировать медленный брокер"""

    def __init__(self, fail_on: set | None = None, delay: float = 0) -> None:
        self.published = []
        self.fail_on = fail_on or set()
        self.delay = delay

    async def publish(self, event) -> None:
        await asyncio.sleep(self.delay)
        if event.id in self.fail_on:
            raise ConnectionError('broker is unavailable')
        self.published.append(event.id)


@pytest.fixture
def publisher():
    return FakePublisher()


@pytest.fixture
def get_events(session):
    async def _get_events() -> dict:
        events = await session.scalars(select(OutboxEvent).execution_options(populate_existing=True))
        return {event.id: event for event in events}

    return _get_events
