import asyncio
from datetime import UTC, datetime

from src.core.database.di import AsyncSessionLocal
from src.outbox.logic.use_cases.publish_outbox_batch import PublishOutboxBatchUseCase
from tests.test_outbox.conftest import FakePublisher
from tests.test_outbox.factories import OutboxEventFactory


async def publish_batch(publisher, batch_size: int = 10) -> int:
    async with AsyncSessionLocal() as session:
        return await PublishOutboxBatchUseCase(session=session, publisher=publisher, batch_size=batch_size).execute()


async def test_publish_batch_publishes_events_in_creation_order(session, publisher):
    events = await OutboxEventFactory.create_batch(session, 3)

    published = await publish_batch(publisher)

    assert published == 3
    assert publisher.published == [event.id for event in events]


async def test_publish_batch_marks_events_published(session, publisher, get_events):
    event = await OutboxEventFactory.create(session)

    await publish_batch(publisher)

    stored = (await get_events())[event.id]
    assert stored.published_at is not None
    assert stored.attempts == 0


async def test_publish_batch_skips_already_published_events(session, publisher):
    await OutboxEventFactory.create(session, published_at=datetime.now(UTC))

    published = await publish_batch(publisher)

    assert published == 0
    assert publisher.published == []


async def test_publish_batch_respects_batch_size(session, publisher):
    events = await OutboxEventFactory.create_batch(session, 3)

    published = await publish_batch(publisher, batch_size=2)

    assert published == 2
    assert publisher.published == [events[0].id, events[1].id]


async def test_publish_batch_on_error_stops_and_records_failure(session, get_events):
    first, failing, last = await OutboxEventFactory.create_batch(session, 3)
    publisher = FakePublisher(fail_on={failing.id})

    published = await publish_batch(publisher)

    stored = await get_events()
    assert published == 1
    assert stored[first.id].published_at is not None
    assert stored[failing.id].published_at is None
    assert stored[failing.id].attempts == 1
    assert 'broker is unavailable' in stored[failing.id].last_error
    assert stored[last.id].published_at is None
    assert stored[last.id].attempts == 0


async def test_failed_event_is_published_by_next_batch(session, get_events):
    event = await OutboxEventFactory.create(session)
    await publish_batch(FakePublisher(fail_on={event.id}))

    published = await publish_batch(FakePublisher())

    assert published == 1
    assert (await get_events())[event.id].published_at is not None


async def test_concurrent_batches_publish_each_event_once(session):
    events = await OutboxEventFactory.create_batch(session, 6)
    publisher = FakePublisher(delay=0.05)

    results = await asyncio.gather(*(publish_batch(publisher, batch_size=3) for _ in range(3)))

    assert sum(results) == 6
    assert sorted(publisher.published) == sorted(event.id for event in events)
