from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.brokers.retry import ATTEMPT_HEADER, DelayedRetryPolicy


def build_message(headers: dict):
    return SimpleNamespace(
        body=b'{"payment_id": "1"}',
        headers=headers,
        content_type='application/json',
        message_id='message-1',
        correlation_id='correlation-1',
    )


@pytest.fixture
def publishers():
    return [AsyncMock(), AsyncMock()]


@pytest.fixture
def policy(publishers):
    return DelayedRetryPolicy(publishers)


def test_max_attempts_is_one_more_than_retry_queues(policy):
    assert policy.max_attempts == 3


@pytest.mark.parametrize(
    ('headers', 'expected_attempt'), [({}, 1), ({ATTEMPT_HEADER: 2}, 2), ({ATTEMPT_HEADER: '3'}, 3)]
)
def test_get_attempt_reads_header(headers, expected_attempt):
    attempt = DelayedRetryPolicy.get_attempt(build_message(headers))

    assert attempt == expected_attempt


@pytest.mark.parametrize(('attempt', 'publisher_index'), [(1, 0), (2, 1)])
async def test_schedule_retry_publishes_to_queue_of_current_attempt(policy, publishers, attempt, publisher_index):
    message = build_message({ATTEMPT_HEADER: attempt})

    scheduled = await policy.schedule_retry(message)

    assert scheduled is True
    publishers[publisher_index].publish.assert_awaited_once_with(
        message.body,
        headers={ATTEMPT_HEADER: attempt + 1},
        content_type='application/json',
        message_id='message-1',
        correlation_id='correlation-1',
        persist=True,
    )


async def test_schedule_retry_on_last_attempt_returns_false(policy, publishers):
    scheduled = await policy.schedule_retry(build_message({ATTEMPT_HEADER: 3}))

    assert scheduled is False
    for publisher in publishers:
        publisher.publish.assert_not_awaited()
