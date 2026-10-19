import uuid

import pytest
from fastapi import status

ENDPOINTS = [
    pytest.param('POST', '/api/v1/payments', id='create'),
    pytest.param('GET', f'/api/v1/payments/{uuid.uuid4()}', id='get'),
]


@pytest.mark.parametrize(('method', 'url'), ENDPOINTS)
@pytest.mark.parametrize(
    'headers',
    [
        pytest.param({}, id='without-key'),
        pytest.param({'X-API-Key': 'wrong-key'}, id='wrong-key'),
    ],
)
async def test_endpoint_without_valid_api_key_returns_401(api_client, method, url, headers):
    response = await api_client.request(method, url, headers=headers)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {'detail': 'Неверный или отсутствующий API-ключ'}


async def test_healthcheck_does_not_require_api_key(api_client):
    response = await api_client.get('/healthcheck')

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'status': 'ok'}
