import pytest

from src.payments.enums import PaymentStatusEnum
from tests.test_payments.factories import WEBHOOK_URL, PaymentFactory


@pytest.fixture
def payment_payload():
    return {
        'amount': '1500.00',
        'currency': 'RUB',
        'description': 'Оплата заказа №42',
        'metadata': {'order_id': 42},
        'webhook_url': WEBHOOK_URL,
    }


@pytest.fixture
async def payment(session):
    return await PaymentFactory.create(session)


@pytest.fixture
async def succeeded_payment(session):
    return await PaymentFactory.create(session, status=PaymentStatusEnum.SUCCEEDED)
