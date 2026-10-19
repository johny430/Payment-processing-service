import typing as t

import httpx
from faststream import Depends

from src.core.clients.http import HTTPXClientProvider
from src.core.settings import settings
from src.payments.clients import EmulatedPaymentGateway, PaymentGateway, WebhookSender

# Один пул соединений на процесс consumer; закрывается в его after_shutdown
webhook_http_client = HTTPXClientProvider(timeout=settings.WEBHOOK_TIMEOUT)


def get_payment_gateway() -> PaymentGateway:
    return EmulatedPaymentGateway()


def get_webhook_sender(client: t.Annotated[httpx.AsyncClient, Depends(webhook_http_client)]) -> WebhookSender:
    return WebhookSender(client)
