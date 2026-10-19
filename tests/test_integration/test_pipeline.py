"""Сквозные сценарии на настоящих PostgreSQL и RabbitMQ: API -> outbox -> relay -> очередь -> consumer -> webhook"""

import asyncio
import json
import time
from uuid import UUID

import pytest

from src.core.brokers.retry import ATTEMPT_HEADER
from src.core.brokers.topology import payments_exchange, queue_payments_new_dlq
from src.core.database.di import AsyncSessionLocal
from src.core.settings import settings
from src.outbox.publisher import RabbitEventPublisher
from src.outbox.relay import OutboxRelay
from src.payments.enums import PaymentStatusEnum
from src.payments.models import Payment
from tests.test_payments.factories import WEBHOOK_URL

TIMEOUT = 15


@pytest.fixture
async def relay(real_rmq_broker):
    relay = OutboxRelay(
        session_factory=AsyncSessionLocal,
        publisher=RabbitEventPublisher(real_rmq_broker, payments_exchange),
        batch_size=settings.OUTBOX_BATCH_SIZE,
        poll_interval=settings.OUTBOX_POLL_INTERVAL,
    )
    relay.start()
    yield relay
    await relay.stop()


@pytest.fixture
async def create_payment(api_auth_client, payment_payload):
    async def _create_payment() -> UUID:
        response = await api_auth_client.post(
            '/api/v1/payments', json=payment_payload, headers={'Idempotency-Key': 'integration-key'}
        )
        return UUID(response.json()['payment_id'])

    return _create_payment


async def wait_for_webhooks(httpx_mock, count: int) -> list:
    async with asyncio.timeout(TIMEOUT):
        while len(requests := httpx_mock.get_requests()) < count:
            await asyncio.sleep(0.05)
    return requests


async def get_dead_letter(broker):
    queue = await broker.declare_queue(queue_payments_new_dlq)
    deadline = time.monotonic() + TIMEOUT
    while (message := await queue.get(no_ack=True, fail=False)) is None:
        assert time.monotonic() < deadline, 'Сообщение не попало в DLQ'
        await asyncio.sleep(0.05)
    return message


async def get_payment(session, payment_id: UUID) -> Payment:
    return await session.get(Payment, payment_id, populate_existing=True)


@pytest.mark.usefixtures('relay')
async def test_created_payment_is_processed_and_webhook_delivered(create_payment, session, httpx_mock):
    httpx_mock.add_response(method='POST', url=WEBHOOK_URL)

    payment_id = await create_payment()

    [webhook] = await wait_for_webhooks(httpx_mock, 1)
    payment = await get_payment(session, payment_id)
    assert payment.status == PaymentStatusEnum.SUCCEEDED
    assert payment.processed_at is not None
    assert json.loads(webhook.content)['payment_id'] == str(payment_id)
    assert json.loads(webhook.content)['status'] == 'succeeded'


@pytest.mark.usefixtures('relay')
async def test_temporary_webhook_failure_is_retried(create_payment, session, httpx_mock):
    httpx_mock.add_response(method='POST', url=WEBHOOK_URL, status_code=503)
    httpx_mock.add_response(method='POST', url=WEBHOOK_URL)

    payment_id = await create_payment()

    webhooks = await wait_for_webhooks(httpx_mock, 2)
    payment = await get_payment(session, payment_id)
    assert len(webhooks) == 2
    assert payment.status == PaymentStatusEnum.SUCCEEDED


@pytest.mark.usefixtures('relay')
async def test_permanently_failing_message_goes_to_dlq_after_max_attempts(
    create_payment, session, httpx_mock, real_rmq_broker
):
    httpx_mock.add_response(method='POST', url=WEBHOOK_URL, status_code=500, is_reusable=True)

    payment_id = await create_payment()

    dead_letter = await get_dead_letter(real_rmq_broker)
    payment = await get_payment(session, payment_id)
    assert json.loads(dead_letter.body)['payment_id'] == str(payment_id)
    assert dead_letter.headers[ATTEMPT_HEADER] == settings.PAYMENT_MAX_ATTEMPTS
    assert len(httpx_mock.get_requests()) == settings.PAYMENT_MAX_ATTEMPTS
    # Платёж проведён один раз, повторялась только доставка webhook
    assert payment.status == PaymentStatusEnum.SUCCEEDED
