import secrets
import typing as t

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.core.settings import settings

api_key_header = APIKeyHeader(name='X-API-Key', auto_error=False, description='Статический API-ключ сервиса')


async def verify_api_key(api_key: t.Annotated[str | None, Security(api_key_header)]) -> None:
    """Проверка статического API-ключа из заголовка X-API-Key"""
    expected = settings.API_KEY.get_secret_value().encode()
    # compare_digest защищает от атаки по времени сравнения
    if api_key is None or not secrets.compare_digest(api_key.encode(), expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Неверный или отсутствующий API-ключ',
            headers={'WWW-Authenticate': 'ApiKey'},
        )
