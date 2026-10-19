import typing as t
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, UrlConstraints

from src.payments.dtos import NewPaymentDTO
from src.payments.enums import CurrencyEnum, PaymentStatusEnum

if t.TYPE_CHECKING:
    from src.payments.dtos import PaymentDTO

WebhookUrl = t.Annotated[AnyHttpUrl, UrlConstraints(max_length=2048, allowed_schemes=['http', 'https'])]
Amount = t.Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2, description='Сумма платежа')]


class PaymentCreateSchema(BaseModel):
    """Запрос на создание платежа"""

    amount: Amount
    currency: CurrencyEnum
    description: t.Annotated[str, Field(min_length=1, max_length=500, description='Описание платежа')]
    metadata: dict[str, t.Any] = Field(default_factory=dict, description='Произвольные данные клиента')
    webhook_url: t.Annotated[WebhookUrl, Field(description='URL для уведомления о результате обработки')]

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'amount': '1500.00',
                    'currency': 'RUB',
                    'description': 'Оплата заказа №42',
                    'metadata': {'order_id': 42},
                    'webhook_url': 'https://merchant.example/webhooks/payments',
                }
            ]
        }
    )

    def to_dto(self, idempotency_key: str) -> NewPaymentDTO:
        return NewPaymentDTO(
            amount=self.amount,
            currency=self.currency,
            description=self.description,
            meta=self.metadata,
            idempotency_key=idempotency_key,
            webhook_url=str(self.webhook_url),
        )


class PaymentAcceptedSchema(BaseModel):
    """Ответ на создание платежа"""

    payment_id: UUID
    status: PaymentStatusEnum
    created_at: datetime

    @classmethod
    def from_dto(cls, payment: 'PaymentDTO') -> 'PaymentAcceptedSchema':
        return cls(payment_id=payment.id, status=payment.status, created_at=payment.created_at)


class PaymentSchema(BaseModel):
    """Детальная информация о платеже"""

    payment_id: UUID
    amount: Decimal
    currency: CurrencyEnum
    description: str
    metadata: dict[str, t.Any]
    status: PaymentStatusEnum
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None

    @classmethod
    def from_dto(cls, payment: 'PaymentDTO') -> 'PaymentSchema':
        return cls(
            payment_id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            description=payment.description,
            metadata=payment.meta,
            status=payment.status,
            idempotency_key=payment.idempotency_key,
            webhook_url=payment.webhook_url,
            created_at=payment.created_at,
            processed_at=payment.processed_at,
        )
