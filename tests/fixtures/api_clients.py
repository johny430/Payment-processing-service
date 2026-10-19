import pytest
from httpx import ASGITransport, AsyncClient

from src.core.settings import settings
from src.main import app


@pytest.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        yield client


@pytest.fixture
def api_auth_client(api_client):
    api_client.headers['X-API-Key'] = settings.API_KEY.get_secret_value()
    return api_client
