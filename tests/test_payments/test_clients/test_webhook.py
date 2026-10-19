import json

import httpx
import pytest

from src.payments.clients import WebhookSender
from src.payments.dtos import PaymentDTO
from src.payments.exceptions import WebhookDeliveryError
from tests.test_payments.factories import WEBHOOK_URL


@pytest.fixture
async def webhook_sender():
    async with httpx.AsyncClient() as client:
        yield WebhookSender(client)


@pytest.fixture
def payment_dto(succeeded_payment):
    return PaymentDTO.model_validate(succeeded_payment)


async def test_send_posts_payment_result(webhook_sender, payment_dto, httpx_mock):
    httpx_mock.add_response(method='POST', url=WEBHOOK_URL)

    await webhook_sender.send(payment_dto)

    request = httpx_mock.get_request()
    assert json.loads(request.content) == {
        'payment_id': str(payment_dto.id),
        'status': 'succeeded',
        'amount': '1500.00',
        'currency': 'RUB',
        'metadata': {'order_id': 42},
        'processed_at': None,
    }


@pytest.mark.parametrize('status_code', [301, 400, 404, 500, 503])
async def test_send_with_non_2xx_response_raises(webhook_sender, payment_dto, httpx_mock, status_code):
    httpx_mock.add_response(method='POST', url=WEBHOOK_URL, status_code=status_code)

    with pytest.raises(WebhookDeliveryError):
        await webhook_sender.send(payment_dto)


@pytest.mark.parametrize('error', [httpx.ConnectError('refused'), httpx.ReadTimeout('timeout')])
async def test_send_with_transport_error_raises(webhook_sender, payment_dto, httpx_mock, error):
    httpx_mock.add_exception(error, method='POST', url=WEBHOOK_URL)

    with pytest.raises(WebhookDeliveryError):
        await webhook_sender.send(payment_dto)
