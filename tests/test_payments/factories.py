import uuid
from decimal import Decimal

import factory

from src.payments.enums import CurrencyEnum, PaymentStatusEnum
from src.payments.models import Payment
from tests.factories import BaseFactory

WEBHOOK_URL = 'https://merchant.example/webhooks/payments'


class PaymentFactory(BaseFactory):
    id = factory.LazyFunction(uuid.uuid4)
    amount = Decimal('1500.00')
    currency = CurrencyEnum.RUB
    description = factory.Faker('sentence')
    meta = factory.LazyFunction(lambda: {'order_id': 42})
    status = PaymentStatusEnum.PENDING
    idempotency_key = factory.LazyFunction(lambda: str(uuid.uuid4()))
    webhook_url = WEBHOOK_URL

    class Meta:
        model = Payment
