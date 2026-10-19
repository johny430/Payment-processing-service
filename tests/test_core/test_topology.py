import pytest

from src.core.brokers.topology import (
    PAYMENTS_NEW_ROUTING_KEY,
    get_retry_delay,
    payments_dlx,
    payments_exchange,
    queue_payments_new,
    queue_payments_new_dlq,
    queues_payments_new_retry,
)
from src.core.settings import settings


@pytest.mark.parametrize(('attempt', 'expected_delay'), [(1, 1.0), (2, 2.0), (3, 4.0), (4, 8.0)])
def test_get_retry_delay_grows_exponentially(attempt, expected_delay):
    delay = get_retry_delay(attempt, base_delay=1.0)

    assert delay == expected_delay


def test_retry_queues_count_is_one_less_than_attempts():
    assert len(queues_payments_new_retry) == settings.PAYMENT_MAX_ATTEMPTS - 1


def test_retry_queues_return_messages_to_main_queue_after_ttl():
    ttls = [queue.arguments['x-message-ttl'] for queue in queues_payments_new_retry]

    assert ttls == [int(get_retry_delay(attempt) * 1000) for attempt in range(1, settings.PAYMENT_MAX_ATTEMPTS)]
    for queue in queues_payments_new_retry:
        assert queue.arguments['x-dead-letter-exchange'] == payments_exchange.name
        assert queue.arguments['x-dead-letter-routing-key'] == PAYMENTS_NEW_ROUTING_KEY


def test_main_queue_dead_letters_to_dlq():
    assert queue_payments_new.arguments['x-dead-letter-exchange'] == payments_dlx.name
    assert queue_payments_new.arguments['x-dead-letter-routing-key'] == queue_payments_new_dlq.routing()
