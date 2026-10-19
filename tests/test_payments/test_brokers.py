import uuid

import pytest

from src.core.brokers.retry import ATTEMPT_HEADER
from src.core.brokers.topology import PAYMENTS_NEW_ROUTING_KEY, payments_exchange
from src.payments.brokers import payments_retry_publishers
from src.payments.enums import PaymentStatusEnum
from src.payments.exceptions import PaymentNotFoundError, WebhookDeliveryError
from src.payments.models import Payment
from tests.test_payments.factories import WEBHOOK_URL


def build_event(payment_id) -> dict:
    return {'event_id': str(uuid.uuid4()), 'payment_id': str(payment_id)}


async def publish_event(broker, event: dict, attempt: int | None = None) -> None:
    headers = {ATTEMPT_HEADER: attempt} if attempt else None
    await broker.publish(event, exchange=payments_exchange, routing_key=PAYMENTS_NEW_ROUTING_KEY, headers=headers)


async def test_process_new_payment_saves_status_and_sends_webhook(rmq_broker, session, payment, httpx_mock):
    httpx_mock.add_response(method='POST', url=WEBHOOK_URL)

    await publish_event(rmq_broker, build_event(payment.id))

    stored = await session.get(Payment, payment.id, populate_existing=True)
    assert stored.status == PaymentStatusEnum.SUCCEEDED
    assert len(httpx_mock.get_requests()) == 1


async def test_process_new_payment_on_error_schedules_delayed_retry(rmq_broker, payment, httpx_mock):
    httpx_mock.add_response(method='POST', url=WEBHOOK_URL, status_code=500)
    event = build_event(payment.id)

    await publish_event(rmq_broker, event)

    payments_retry_publishers[0].mock.assert_called_once_with(event)
    payments_retry_publishers[1].mock.assert_not_called()


async def test_process_new_payment_on_second_attempt_uses_next_retry_queue(rmq_broker, payment, httpx_mock):
    httpx_mock.add_response(method='POST', url=WEBHOOK_URL, status_code=500)
    event = build_event(payment.id)

    await publish_event(rmq_broker, event, attempt=2)

    payments_retry_publishers[0].mock.assert_not_called()
    payments_retry_publishers[1].mock.assert_called_once_with(event)


async def test_process_new_payment_on_last_attempt_raises_for_dlq(rmq_broker, payment, httpx_mock):
    httpx_mock.add_response(method='POST', url=WEBHOOK_URL, status_code=500)

    with pytest.raises(WebhookDeliveryError):
        await publish_event(rmq_broker, build_event(payment.id), attempt=3)

    for publisher in payments_retry_publishers:
        publisher.mock.assert_not_called()


async def test_process_new_payment_for_unknown_payment_raises_without_retry(rmq_broker):
    with pytest.raises(PaymentNotFoundError):
        await publish_event(rmq_broker, build_event(uuid.uuid4()))

    payments_retry_publishers[0].mock.assert_not_called()
