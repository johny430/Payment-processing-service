import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update

from src.core.database.di import AsyncSessionLocal
from src.payments.clients import WebhookSender
from src.payments.enums import PaymentStatusEnum
from src.payments.exceptions import PaymentNotFoundError, WebhookDeliveryError
from src.payments.logic.use_cases import ProcessPaymentUseCase
from src.payments.models import Payment


class StubGateway:
    def __init__(self, status: PaymentStatusEnum) -> None:
        self.status = status
        self.charged = []

    async def charge(self, payment):
        self.charged.append(payment.id)
        return self.status


class ConcurrentlyProcessedGateway(StubGateway):
    """Пока шлюз «думает», платёж успевает обработать другой consumer"""

    def __init__(self, status: PaymentStatusEnum, concurrent_status: PaymentStatusEnum) -> None:
        super().__init__(status)
        self.concurrent_status = concurrent_status

    async def charge(self, payment):
        async with AsyncSessionLocal() as session:
            await session.execute(update(Payment).where(Payment.id == payment.id).values(status=self.concurrent_status))
            await session.commit()
        return await super().charge(payment)


@pytest.fixture
def webhook_sender():
    return AsyncMock(spec=WebhookSender)


def build_use_case(session, payment_id, gateway, webhook_sender):
    return ProcessPaymentUseCase(session=session, payment_id=payment_id, gateway=gateway, webhook_sender=webhook_sender)


@pytest.mark.parametrize('gateway_status', [PaymentStatusEnum.SUCCEEDED, PaymentStatusEnum.FAILED])
async def test_process_pending_payment_saves_gateway_status(session, payment, webhook_sender, gateway_status):
    use_case = build_use_case(session, payment.id, StubGateway(gateway_status), webhook_sender)

    result = await use_case.execute()

    stored = await session.get(Payment, payment.id, populate_existing=True)
    assert result.status == gateway_status
    assert stored.status == gateway_status
    assert stored.processed_at is not None


async def test_process_pending_payment_sends_webhook_with_result(session, payment, webhook_sender):
    use_case = build_use_case(session, payment.id, StubGateway(PaymentStatusEnum.SUCCEEDED), webhook_sender)

    result = await use_case.execute()

    webhook_sender.send.assert_awaited_once_with(result)


async def test_process_already_processed_payment_does_not_charge_again(session, succeeded_payment, webhook_sender):
    gateway = StubGateway(PaymentStatusEnum.FAILED)
    use_case = build_use_case(session, succeeded_payment.id, gateway, webhook_sender)

    result = await use_case.execute()

    assert gateway.charged == []
    assert result.status == PaymentStatusEnum.SUCCEEDED
    webhook_sender.send.assert_awaited_once_with(result)


async def test_process_payment_finalized_concurrently_keeps_stored_status(session, payment, webhook_sender):
    gateway = ConcurrentlyProcessedGateway(PaymentStatusEnum.SUCCEEDED, concurrent_status=PaymentStatusEnum.FAILED)
    use_case = build_use_case(session, payment.id, gateway, webhook_sender)

    result = await use_case.execute()

    assert result.status == PaymentStatusEnum.FAILED
    webhook_sender.send.assert_awaited_once_with(result)


async def test_process_unknown_payment_raises_not_found(session, webhook_sender):
    use_case = build_use_case(session, uuid.uuid4(), StubGateway(PaymentStatusEnum.SUCCEEDED), webhook_sender)

    with pytest.raises(PaymentNotFoundError):
        await use_case.execute()


async def test_process_payment_with_webhook_error_keeps_saved_status(session, payment, webhook_sender):
    webhook_sender.send.side_effect = WebhookDeliveryError
    use_case = build_use_case(session, payment.id, StubGateway(PaymentStatusEnum.SUCCEEDED), webhook_sender)

    with pytest.raises(WebhookDeliveryError):
        await use_case.execute()

    stored = await session.get(Payment, payment.id, populate_existing=True)
    assert stored.status == PaymentStatusEnum.SUCCEEDED
