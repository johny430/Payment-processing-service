import typing as t
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from src.payments.enums import CurrencyEnum, PaymentStatusEnum

if t.TYPE_CHECKING:
    from src.payments.dtos import PaymentDTO


class PaymentWebhookSchema(BaseModel):
    """Тело webhook-уведомления о результате обработки платежа"""

    payment_id: UUID
    status: PaymentStatusEnum
    amount: Decimal
    currency: CurrencyEnum
    metadata: dict[str, t.Any]
    processed_at: datetime | None

    @classmethod
    def from_dto(cls, payment: 'PaymentDTO') -> 'PaymentWebhookSchema':
        return cls(
            payment_id=payment.id,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            metadata=payment.meta,
            processed_at=payment.processed_at,
        )
