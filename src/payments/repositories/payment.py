import typing as t
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from src.payments.dtos import PaymentDTO
from src.payments.enums import PaymentStatusEnum
from src.payments.models import Payment

if t.TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.payments.dtos import NewPaymentDTO


class PaymentRepository:
    def __init__(self, session: 'AsyncSession') -> None:
        self.session = session

    async def get_by_id(self, payment_id: UUID) -> PaymentDTO | None:
        """Получение платежа по ID (всегда из БД, а не из identity map сессии)"""
        payment = await self.session.get(Payment, payment_id, populate_existing=True)
        return PaymentDTO.model_validate(payment) if payment else None

    async def get_by_idempotency_key(self, idempotency_key: str) -> PaymentDTO | None:
        """Получение платежа по ключу идемпотентности"""
        stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
        payment = await self.session.scalar(stmt)
        return PaymentDTO.model_validate(payment) if payment else None

    async def create_if_not_exists(self, data: 'NewPaymentDTO') -> PaymentDTO | None:
        """
        Создание платежа, если ключ идемпотентности ещё не занят.

        INSERT ... ON CONFLICT DO NOTHING атомарен: при гонке двух запросов с одним ключом
        запись создаст только один, второй получит None, не ловя IntegrityError.
        """
        stmt = (
            insert(Payment)
            .values(**data.model_dump())
            .on_conflict_do_nothing(index_elements=[Payment.idempotency_key])
            .returning(Payment)
        )
        payment = await self.session.scalar(stmt)
        return PaymentDTO.model_validate(payment) if payment else None

    async def finalize(self, payment_id: UUID, status: PaymentStatusEnum) -> PaymentDTO | None:
        """
        Перевод платежа из pending в итоговый статус.

        Условие на status = pending делает переход однократным: если платёж уже обработал
        другой consumer (повторная доставка сообщения), вернётся None.
        """
        stmt = (
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == PaymentStatusEnum.PENDING)
            .values(status=status, processed_at=func.now())
            .returning(Payment)
        )
        payment = await self.session.scalar(stmt)
        return PaymentDTO.model_validate(payment) if payment else None
