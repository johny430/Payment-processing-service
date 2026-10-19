import uuid
from decimal import Decimal

import pytest

from src.payments.dtos import NewPaymentDTO
from src.payments.enums import CurrencyEnum, PaymentStatusEnum
from src.payments.repositories import PaymentRepository
from tests.test_payments.factories import WEBHOOK_URL


@pytest.fixture
def repository(session):
    return PaymentRepository(session)


@pytest.fixture
def new_payment():
    return NewPaymentDTO(
        amount=Decimal('10.50'),
        currency=CurrencyEnum.EUR,
        description='Подписка',
        meta={},
        idempotency_key='key-1',
        webhook_url=WEBHOOK_URL,
    )


async def test_create_if_not_exists_creates_pending_payment(repository, new_payment):
    payment = await repository.create_if_not_exists(new_payment)

    assert payment.status == PaymentStatusEnum.PENDING
    assert payment.amount == Decimal('10.50')
    assert payment.created_at is not None


async def test_create_if_not_exists_with_taken_key_returns_none(repository, new_payment):
    await repository.create_if_not_exists(new_payment)

    payment = await repository.create_if_not_exists(new_payment)

    assert payment is None


async def test_get_by_id_returns_none_for_unknown_payment(repository):
    payment = await repository.get_by_id(uuid.uuid4())

    assert payment is None


async def test_get_by_idempotency_key_returns_payment(repository, payment):
    found = await repository.get_by_idempotency_key(payment.idempotency_key)

    assert found.id == payment.id


async def test_finalize_pending_payment_sets_status_and_processed_at(repository, payment):
    finalized = await repository.finalize(payment.id, PaymentStatusEnum.FAILED)

    assert finalized.status == PaymentStatusEnum.FAILED
    assert finalized.processed_at is not None


async def test_finalize_already_processed_payment_returns_none(repository, succeeded_payment):
    finalized = await repository.finalize(succeeded_payment.id, PaymentStatusEnum.FAILED)

    stored = await repository.get_by_id(succeeded_payment.id)
    assert finalized is None
    assert stored.status == PaymentStatusEnum.SUCCEEDED
