import typing as t
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.base import Base, CreatedAtMixin
from src.payments.enums import CurrencyEnum, PaymentStatusEnum


class Payment(CreatedAtMixin, Base):
    """Платёж"""

    __tablename__ = 'payments'
    __table_args__ = (CheckConstraint('amount > 0', name='amount_positive'),)
    __mapper_args__ = {'eager_defaults': True}  # server_default (created_at) читается сразу через RETURNING

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, comment='Идентификатор платежа')
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), comment='Сумма')
    currency: Mapped[CurrencyEnum] = mapped_column(String(3), comment='Валюта')
    description: Mapped[str] = mapped_column(String(500), comment='Описание')
    # Атрибут называется meta, потому что metadata зарезервировано в Declarative API
    meta: Mapped[dict[str, t.Any]] = mapped_column(
        'metadata', server_default=text("'{}'::jsonb"), comment='Дополнительные данные клиента'
    )
    status: Mapped[PaymentStatusEnum] = mapped_column(
        String(16), default=PaymentStatusEnum.PENDING, index=True, comment='Статус'
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, comment='Ключ идемпотентности')
    webhook_url: Mapped[str] = mapped_column(String(2048), comment='URL для уведомления о результате')
    processed_at: Mapped[datetime | None] = mapped_column(comment='Дата обработки')
