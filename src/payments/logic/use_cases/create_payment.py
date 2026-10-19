import typing as t
import uuid

from src.core.brokers.topology import PAYMENTS_NEW_ROUTING_KEY
from src.core.settings.log import get_logger
from src.core.use_cases.base import BaseSessionAsyncUseCase
from src.outbox.repositories import OutboxRepository
from src.payments.dtos import NewPaymentDTO
from src.payments.exceptions import IdempotencyKeyConflictError, PaymentNotFoundError
from src.payments.repositories import PaymentRepository
from src.payments.schemas import PaymentCreatedEventSchema

if t.TYPE_CHECKING:
    from src.payments.dtos import PaymentDTO

logger = get_logger(__name__)


class CreatePaymentUseCase(BaseSessionAsyncUseCase):
    """
    Создание платежа с защитой от дублей по Idempotency-Key.

    Платёж и событие payments.new пишутся в одной транзакции (transactional outbox).
    Повторный запрос с тем же ключом и теми же параметрами возвращает уже созданный платёж,
    с другими параметрами — IdempotencyKeyConflictError. Гонка одновременных запросов
    разрешается уникальным индексом и INSERT ... ON CONFLICT DO NOTHING.
    """

    def __init__(
        self,
        data: NewPaymentDTO,
        payment_repo: type[PaymentRepository] = PaymentRepository,
        outbox_repo: type[OutboxRepository] = OutboxRepository,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.data = data
        self.payment_repo = payment_repo(self.session)
        self.outbox_repo = outbox_repo(self.session)

    async def execute(self) -> 'PaymentDTO':
        payment = await self.payment_repo.create_if_not_exists(self.data)
        if payment is None:
            return await self._get_existing_payment()

        event = PaymentCreatedEventSchema(event_id=uuid.uuid4(), payment_id=payment.id)
        self.outbox_repo.add(
            event_id=event.event_id,
            event_type=PAYMENTS_NEW_ROUTING_KEY,
            payload=event.model_dump(mode='json'),
        )
        await self.session.commit()
        logger.info('Платёж создан', payment_id=str(payment.id))
        return payment

    async def _get_existing_payment(self) -> 'PaymentDTO':
        """Платёж, ранее созданный с этим ключом (в том числе конкурентным запросом)"""
        # READ COMMITTED: ON CONFLICT дожидается конкурирующей транзакции, поэтому её запись уже видна
        payment = await self.payment_repo.get_by_idempotency_key(self.data.idempotency_key)
        if payment is None:  # pragma: no cover - ключ занят, а платежи не удаляются
            raise PaymentNotFoundError

        # Повтор допустим только с теми же параметрами: сравниваются все поля, из которых создавался платёж
        if NewPaymentDTO.model_validate(payment) != self.data:
            raise IdempotencyKeyConflictError
        logger.info('Повторный запрос по Idempotency-Key', payment_id=str(payment.id))
        return payment
