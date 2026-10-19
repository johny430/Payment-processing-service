import typing as t

from faststream import Depends
from faststream.rabbit import RabbitRouter
from faststream.rabbit.annotations import RabbitMessage
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.brokers.retry import DelayedRetryPolicy
from src.core.brokers.topology import (
    payments_exchange,
    payments_retry_exchange,
    queue_payments_new,
    queues_payments_new_retry,
)
from src.core.database.di import get_db_session
from src.core.settings.log import get_logger
from src.payments.clients import PaymentGateway, WebhookSender
from src.payments.di import get_payment_gateway, get_webhook_sender
from src.payments.exceptions import PaymentNotFoundError
from src.payments.logic.use_cases import ProcessPaymentUseCase
from src.payments.schemas import PaymentCreatedEventSchema

logger = get_logger(__name__)

payments_rmq_router = RabbitRouter()

payments_retry_publishers = tuple(
    payments_rmq_router.publisher(
        queue,
        exchange=payments_retry_exchange,
        description=f'Отложенный повтор обработки платежа после попытки {attempt}',
    )
    for attempt, queue in enumerate(queues_payments_new_retry, start=1)
)
payments_retry_policy = DelayedRetryPolicy(payments_retry_publishers)


@payments_rmq_router.subscriber(
    queue_payments_new,
    payments_exchange,
    description='Обработка новых платежей: шлюз, обновление статуса, webhook',
)
async def process_new_payment(
    event: PaymentCreatedEventSchema,
    message: RabbitMessage,
    session: t.Annotated[AsyncSession, Depends(get_db_session)],
    gateway: t.Annotated[PaymentGateway, Depends(get_payment_gateway)],
    webhook_sender: t.Annotated[WebhookSender, Depends(get_webhook_sender)],
) -> None:
    """
    Единственный обработчик очереди payments.new.

    Ошибка обработки отправляет сообщение на отложенный повтор; когда попытки исчерпаны
    (или платёж не найден и повтор бессмыслен), исключение пробрасывается — FastStream делает
    reject без requeue, и RabbitMQ перекладывает сообщение в DLQ.
    """
    log = logger.bind(payment_id=str(event.payment_id), attempt=payments_retry_policy.get_attempt(message))
    use_case = ProcessPaymentUseCase(
        session=session,
        payment_id=event.payment_id,
        gateway=gateway,
        webhook_sender=webhook_sender,
    )
    try:
        await use_case.execute()
    except PaymentNotFoundError:
        log.error('Платёж из события не найден, сообщение уходит в DLQ')
        raise
    except Exception:
        log.exception('Ошибка обработки платежа')
        if not await payments_retry_policy.schedule_retry(message):
            raise
