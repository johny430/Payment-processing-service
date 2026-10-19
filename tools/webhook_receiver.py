"""
Демонстрационный приёмник webhook для docker compose.

POST /webhook       — принимает уведомление (200)
POST /webhook/fail  — всегда отвечает 500, чтобы показать retry и попадание сообщения в DLQ
GET  /webhooks      — полученные уведомления (в памяти процесса)
"""

import logging
import typing as t

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger('uvicorn.error')

app = FastAPI(title='Webhook receiver (demo)')
received: list[dict[str, t.Any]] = []


@app.post('/webhook')
async def receive_webhook(request: Request) -> dict[str, str]:
    payload = await request.json()
    received.append(payload)
    logger.info('Получен webhook: %s', payload)
    return {'status': 'received'}


@app.post('/webhook/fail')
async def fail_webhook(request: Request) -> JSONResponse:
    logger.info('Webhook отклонён (демонстрация retry): %s', await request.json())
    return JSONResponse({'status': 'error'}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.get('/webhooks')
async def list_webhooks() -> list[dict[str, t.Any]]:
    return received
