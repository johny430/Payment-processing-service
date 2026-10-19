import typing as t
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from src.core.schemas.base import BaseFromAttrsModel
from src.payments.enums import CurrencyEnum, PaymentStatusEnum


class PaymentDTO(BaseFromAttrsModel):
    id: UUID
    amount: Decimal
    currency: CurrencyEnum
    description: str
    meta: dict[str, t.Any]
    status: PaymentStatusEnum
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None


class NewPaymentDTO(BaseFromAttrsModel):
    """Данные для создания платежа"""

    amount: Decimal
    currency: CurrencyEnum
    description: str
    meta: dict[str, t.Any]
    idempotency_key: str
    webhook_url: str
