import uuid
from datetime import UTC, datetime, timedelta

import factory

from src.core.brokers.topology import PAYMENTS_NEW_ROUTING_KEY
from src.outbox.models import OutboxEvent
from tests.factories import BaseFactory

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


class OutboxEventFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    event_type = PAYMENTS_NEW_ROUTING_KEY
    payload = factory.LazyAttribute(lambda event: {'event_id': str(event.id), 'payment_id': str(uuid.uuid4())})
    # Явное время создания делает порядок выборки детерминированным
    created_at = factory.Sequence(lambda n: BASE_TIME + timedelta(seconds=n))

    class Meta:
        model = OutboxEvent
