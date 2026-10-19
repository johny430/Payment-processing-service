import random

import pytest

from src.payments.clients import EmulatedPaymentGateway
from src.payments.enums import PaymentStatusEnum


@pytest.fixture
def sleep_mock(mocker):
    return mocker.patch('src.payments.clients.gateway.asyncio.sleep')


@pytest.mark.parametrize(
    ('success_rate', 'expected_status'),
    [(1.0, PaymentStatusEnum.SUCCEEDED), (0.0, PaymentStatusEnum.FAILED)],
)
async def test_charge_returns_status_by_success_rate(payment, sleep_mock, success_rate, expected_status):
    gateway = EmulatedPaymentGateway(min_delay=2, max_delay=5, success_rate=success_rate)

    status = await gateway.charge(payment)

    assert status == expected_status


async def test_charge_waits_between_min_and_max_delay(payment, sleep_mock):
    gateway = EmulatedPaymentGateway(min_delay=2, max_delay=5, success_rate=0.9, rng=random.Random(1))

    for _ in range(50):
        await gateway.charge(payment)

    delays = [call.args[0] for call in sleep_mock.await_args_list]
    assert all(2 <= delay <= 5 for delay in delays)


async def test_charge_succeeds_in_about_ninety_percent_of_cases(payment, sleep_mock):
    gateway = EmulatedPaymentGateway(min_delay=2, max_delay=5, success_rate=0.9, rng=random.Random(42))

    statuses = [await gateway.charge(payment) for _ in range(1000)]

    success_share = statuses.count(PaymentStatusEnum.SUCCEEDED) / len(statuses)
    assert 0.87 <= success_share <= 0.93
