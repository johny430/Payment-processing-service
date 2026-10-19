from decimal import Decimal
from uuid import UUID

import pytest
from fastapi import status
from sqlalchemy import func, select

from src.core.brokers.topology import PAYMENTS_NEW_ROUTING_KEY
from src.outbox.models import OutboxEvent
from src.payments.models import Payment

URL = '/api/v1/payments'


async def count(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def test_create_payment_returns_202_with_pending_status(api_auth_client, payment_payload):
    response = await api_auth_client.post(URL, json=payment_payload, headers={'Idempotency-Key': 'key-1'})

    data = response.json()
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert set(data) == {'payment_id', 'status', 'created_at'}
    assert data['status'] == 'pending'


async def test_create_payment_saves_payment(api_auth_client, payment_payload, session):
    response = await api_auth_client.post(URL, json=payment_payload, headers={'Idempotency-Key': 'key-1'})

    payment = await session.get(Payment, UUID(response.json()['payment_id']))
    assert payment.amount == Decimal('1500.00')
    assert payment.currency == 'RUB'
    assert payment.description == payment_payload['description']
    assert payment.meta == payment_payload['metadata']
    assert payment.webhook_url == payment_payload['webhook_url']
    assert payment.idempotency_key == 'key-1'
    assert payment.processed_at is None


async def test_create_payment_writes_outbox_event_in_same_transaction(api_auth_client, payment_payload, session):
    response = await api_auth_client.post(URL, json=payment_payload, headers={'Idempotency-Key': 'key-1'})

    event = await session.scalar(select(OutboxEvent))
    assert event.event_type == PAYMENTS_NEW_ROUTING_KEY
    assert event.payload == {'event_id': str(event.id), 'payment_id': response.json()['payment_id']}
    assert event.published_at is None


async def test_create_payment_with_same_idempotency_key_returns_same_payment(api_auth_client, payment_payload, session):
    first = await api_auth_client.post(URL, json=payment_payload, headers={'Idempotency-Key': 'key-1'})

    second = await api_auth_client.post(URL, json=payment_payload, headers={'Idempotency-Key': 'key-1'})

    assert second.status_code == status.HTTP_202_ACCEPTED
    assert second.json() == first.json()
    assert await count(session, Payment) == 1
    assert await count(session, OutboxEvent) == 1


async def test_create_payment_with_different_idempotency_keys_creates_two_payments(
    api_auth_client, payment_payload, session
):
    first = await api_auth_client.post(URL, json=payment_payload, headers={'Idempotency-Key': 'key-1'})

    second = await api_auth_client.post(URL, json=payment_payload, headers={'Idempotency-Key': 'key-2'})

    assert first.json()['payment_id'] != second.json()['payment_id']
    assert await count(session, Payment) == 2
    assert await count(session, OutboxEvent) == 2


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('amount', '99.99'),
        ('currency', 'USD'),
        ('description', 'Другое описание'),
        ('metadata', {'order_id': 43}),
        ('webhook_url', 'https://other.example/hook'),
    ],
)
async def test_create_payment_with_same_key_and_other_params_returns_422(
    api_auth_client, payment_payload, session, field, value
):
    await api_auth_client.post(URL, json=payment_payload, headers={'Idempotency-Key': 'key-1'})

    response = await api_auth_client.post(
        URL, json=payment_payload | {field: value}, headers={'Idempotency-Key': 'key-1'}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {'detail': 'Idempotency-Key уже использован для запроса с другими параметрами'}
    assert await count(session, Payment) == 1


async def test_create_payment_with_equal_amount_in_other_notation_is_idempotent(api_auth_client, payment_payload):
    first = await api_auth_client.post(URL, json=payment_payload, headers={'Idempotency-Key': 'key-1'})

    second = await api_auth_client.post(
        URL, json=payment_payload | {'amount': 1500}, headers={'Idempotency-Key': 'key-1'}
    )

    assert second.status_code == status.HTTP_202_ACCEPTED
    assert second.json()['payment_id'] == first.json()['payment_id']


@pytest.mark.parametrize(
    'headers',
    [
        pytest.param({}, id='missing'),
        pytest.param({'Idempotency-Key': ''}, id='empty'),
        pytest.param({'Idempotency-Key': 'k' * 256}, id='too-long'),
    ],
)
async def test_create_payment_with_invalid_idempotency_key_returns_422(
    api_auth_client, payment_payload, session, headers
):
    response = await api_auth_client.post(URL, json=payment_payload, headers=headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert await count(session, Payment) == 0


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('amount', '0'),
        ('amount', '-10.00'),
        ('amount', '10.001'),
        ('amount', 'abc'),
        ('currency', 'GBP'),
        ('description', ''),
        ('description', 'x' * 501),
        ('metadata', ['not', 'an', 'object']),
        ('webhook_url', 'not-a-url'),
        ('webhook_url', 'ftp://merchant.example/hook'),
    ],
)
async def test_create_payment_with_invalid_body_returns_422(api_auth_client, payment_payload, field, value):
    response = await api_auth_client.post(
        URL, json=payment_payload | {field: value}, headers={'Idempotency-Key': 'key-1'}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()['detail'][0]['loc'] == ['body', field]


@pytest.mark.parametrize('field', ['amount', 'currency', 'description', 'webhook_url'])
async def test_create_payment_without_required_field_returns_422(api_auth_client, payment_payload, field):
    payment_payload.pop(field)

    response = await api_auth_client.post(URL, json=payment_payload, headers={'Idempotency-Key': 'key-1'})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_create_payment_without_metadata_uses_empty_object(api_auth_client, payment_payload, session):
    payment_payload.pop('metadata')

    response = await api_auth_client.post(URL, json=payment_payload, headers={'Idempotency-Key': 'key-1'})

    payment = await session.get(Payment, UUID(response.json()['payment_id']))
    assert payment.meta == {}
