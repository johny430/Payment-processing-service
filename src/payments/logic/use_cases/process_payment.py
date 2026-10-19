import typing as t

from src.core.settings.log import get_logger
from src.core.use_cases.base import BaseSessionAsyncUseCase
from src.payments.enums import PaymentStatusEnum
from src.payments.exceptions import PaymentNotFoundError
from src.payments.repositories import PaymentRepository

if t.TYPE_CHECKING:
    from uuid import UUID

    from src.payments.clients import PaymentGateway, WebhookSender
    from src.payments.dtos import PaymentDTO

logger = get_logger(__name__)


class ProcessPaymentUseCase(BaseSessionAsyncUseCase):
    """
    Обработка платежа: проведение через шлюз, фиксация статуса и webhook-уведомление.

    Сценарий идемпотентен, поэтому безопасен при повторной доставке сообщения и при retry:
    шлюз вызывается только для платежа в статусе pending, а переход в итоговый статус
    выполняется условным UPDATE. Если упала только отправка webhook, повтор не проводит
    платёж заново, а лишь повторно отправляет уведомление (доставка webhook — at-least-once).
    """

    def __init__(
        self,
        payment_id: 'UUID',
        gateway: 'PaymentGateway',
        webhook_sender: 'WebhookSender',
        payment_repo: type[PaymentRepository] = PaymentRepository,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.payment_id = payment_id
        self.gateway = gateway
        self.webhook_sender = webhook_sender
        self.payment_repo = payment_repo(self.session)

    async def execute(self) -> 'PaymentDTO':
        payment = await self._get_payment()
        if payment.status == PaymentStatusEnum.PENDING:
            payment = await self._charge(payment)

        await self.webhook_sender.send(payment)
        logger.info('Webhook отправлен', payment_id=str(payment.id), status=payment.status)
        return payment

    async def _get_payment(self) -> 'PaymentDTO':
        payment = await self.payment_repo.get_by_id(self.payment_id)
        # Завершаем читающую транзакцию, чтобы не держать соединение во время долгого запроса в шлюз
        await self.session.commit()
        if payment is None:
            raise PaymentNotFoundError
        return payment

    async def _charge(self, payment: 'PaymentDTO') -> 'PaymentDTO':
        status = await self.gateway.charge(payment)
        finalized = await self.payment_repo.finalize(payment.id, status)
        await self.session.commit()

        if finalized is None:
            # Платёж параллельно обработал другой consumer — берём зафиксированный им результат
            logger.info('Платёж уже обработан', payment_id=str(payment.id))
            return await self._get_payment()

        logger.info('Платёж обработан', payment_id=str(payment.id), status=finalized.status)
        return finalized
