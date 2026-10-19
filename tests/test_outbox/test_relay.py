import asyncio

import pytest

from src.core.database.di import AsyncSessionLocal
from src.outbox.relay import OutboxRelay
from tests.test_outbox.conftest import FakePublisher
from tests.test_outbox.factories import OutboxEventFactory


@pytest.fixture
async def run_relay():
    relays = []

    def _run_relay(publisher, batch_size: int = 10) -> OutboxRelay:
        relay = OutboxRelay(AsyncSessionLocal, publisher, batch_size=batch_size, poll_interval=0.01)
        relay.start()
        relays.append(relay)
        return relay

    yield _run_relay

    for relay in relays:
        await relay.stop()


async def wait_until_published(publisher, count: int, timeout: float = 5) -> None:
    async with asyncio.timeout(timeout):
        while len(publisher.published) < count:
            await asyncio.sleep(0.01)


async def test_relay_publishes_new_events(session, publisher, run_relay):
    run_relay(publisher)

    event = await OutboxEventFactory.create(session)

    await wait_until_published(publisher, 1)
    assert publisher.published == [event.id]


async def test_relay_publishes_backlog_larger_than_batch(session, publisher, run_relay):
    events = await OutboxEventFactory.create_batch(session, 5)

    run_relay(publisher, batch_size=2)

    await wait_until_published(publisher, 5)
    assert publisher.published == [event.id for event in events]


async def test_relay_keeps_running_after_publish_error(session, run_relay):
    event = await OutboxEventFactory.create(session)
    publisher = FakePublisher(fail_on={event.id})
    run_relay(publisher)
    await asyncio.sleep(0.05)

    publisher.fail_on.clear()

    await wait_until_published(publisher, 1)
    assert publisher.published == [event.id]


async def test_relay_stop_finishes_loop(publisher):
    relay = OutboxRelay(AsyncSessionLocal, publisher, batch_size=10, poll_interval=60)
    relay.start()

    await asyncio.wait_for(relay.stop(), timeout=1)


class FlakySessionFactory:
    """Первое обращение к БД падает, дальше — обычные сессии"""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError('database is unavailable')
        return AsyncSessionLocal()


async def test_relay_keeps_running_after_database_error(session, publisher):
    event = await OutboxEventFactory.create(session)
    relay = OutboxRelay(FlakySessionFactory(), publisher, batch_size=10, poll_interval=0.01)

    relay.start()
    await wait_until_published(publisher, 1)
    await relay.stop()

    assert publisher.published == [event.id]
