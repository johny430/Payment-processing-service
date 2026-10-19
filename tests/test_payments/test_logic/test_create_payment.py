import asyncio

from sqlalchemy import func, select

from src.core.database.di import AsyncSessionLocal
from src.outbox.models import OutboxEvent
from src.payments.logic.use_cases import CreatePaymentUseCase
from src.payments.models import Payment
from src.payments.schemas import PaymentCreateSchema


async def create_payment(idempotency_key: str, payload: dict):
    async with AsyncSessionLocal() as session:
        data = PaymentCreateSchema.model_validate(payload).to_dto(idempotency_key)
        use_case = CreatePaymentUseCase(session=session, data=data)
        return await use_case.execute()


async def test_concurrent_requests_with_same_key_create_one_payment(payment_payload, session):
    payments = await asyncio.gather(*(create_payment('race-key', payment_payload) for _ in range(10)))

    assert len({payment.id for payment in payments}) == 1
    assert await session.scalar(select(func.count()).select_from(Payment)) == 1
    assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 1
