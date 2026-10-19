import typing as t

import httpx

from src.payments.exceptions import WebhookDeliveryError
from src.payments.schemas import PaymentWebhookSchema

if t.TYPE_CHECKING:
    from src.payments.dtos import PaymentDTO


class WebhookSender:
    """Отправка webhook-уведомлений о результате обработки платежа"""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def send(self, payment: 'PaymentDTO') -> None:
        """POST на webhook_url платежа; любой ответ кроме 2xx или сетевая ошибка — WebhookDeliveryError"""
        payload = PaymentWebhookSchema.from_dto(payment).model_dump(mode='json')
        try:
            response = await self.client.post(payment.webhook_url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as err:
            raise WebhookDeliveryError(f'Webhook для платежа {payment.id} не доставлен: {err}') from err
