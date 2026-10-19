import uuid

from fastapi import status


async def test_get_payment_returns_payment_details(api_auth_client, payment):
    response = await api_auth_client.get(f'/api/v1/payments/{payment.id}')

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        'payment_id': str(payment.id),
        'amount': '1500.00',
        'currency': 'RUB',
        'description': payment.description,
        'metadata': {'order_id': 42},
        'status': 'pending',
        'idempotency_key': payment.idempotency_key,
        'webhook_url': payment.webhook_url,
        'created_at': payment.created_at.isoformat().replace('+00:00', 'Z'),
        'processed_at': None,
    }


async def test_get_payment_returns_404_for_unknown_payment(api_auth_client):
    response = await api_auth_client.get(f'/api/v1/payments/{uuid.uuid4()}')

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {'detail': 'Платёж не найден'}


async def test_get_payment_returns_422_for_invalid_id(api_auth_client):
    response = await api_auth_client.get('/api/v1/payments/not-a-uuid')

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
