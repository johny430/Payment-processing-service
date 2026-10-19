"""
Топология RabbitMQ для событий о новых платежах.

    payments (direct) --payments.new--> [payments.new] --> consumer
                                              | reject после последней попытки
                                              v
    payments.dlx (direct) --payments.new--> [payments.new.dlq]

    payments.retry (direct) --payments.new.retry.N--> [payments.new.retry.N] (TTL = base * 2^(N-1))
                                                           | по истечении TTL
                                                           v
                                                payments --payments.new--> [payments.new]

Для каждой ступени задержки — своя очередь с фиксированным TTL: в одной очереди с разными
per-message TTL сообщения истекают только из головы очереди, и короткая задержка ждала бы длинную.
"""

import typing as t

from faststream.rabbit import ExchangeType, RabbitExchange, RabbitQueue

from src.core.settings import settings

if t.TYPE_CHECKING:
    from faststream.rabbit import RabbitBroker

PAYMENTS_NEW_ROUTING_KEY = settings.QUEUE_PAYMENTS_NEW


def get_retry_delay(attempt: int, base_delay: float = settings.PAYMENT_RETRY_BASE_DELAY) -> float:
    """Задержка (секунды) перед повтором после неудачной попытки с номером attempt"""
    return base_delay * 2.0 ** (attempt - 1)


payments_exchange = RabbitExchange(settings.RABBITMQ_PAYMENTS_EXCHANGE, type=ExchangeType.DIRECT, durable=True)
payments_dlx = RabbitExchange(f'{settings.RABBITMQ_PAYMENTS_EXCHANGE}.dlx', type=ExchangeType.DIRECT, durable=True)
payments_retry_exchange = RabbitExchange(
    f'{settings.RABBITMQ_PAYMENTS_EXCHANGE}.retry', type=ExchangeType.DIRECT, durable=True
)

queue_payments_new = RabbitQueue(
    settings.QUEUE_PAYMENTS_NEW,
    durable=True,
    arguments={
        'x-dead-letter-exchange': payments_dlx.name,
        'x-dead-letter-routing-key': PAYMENTS_NEW_ROUTING_KEY,
    },
)
queue_payments_new_dlq = RabbitQueue(
    f'{settings.QUEUE_PAYMENTS_NEW}.dlq',
    durable=True,
    routing_key=PAYMENTS_NEW_ROUTING_KEY,
)
# Очередь N принимает сообщения после неудачной попытки N, поэтому их на одну меньше, чем попыток
queues_payments_new_retry = tuple(
    RabbitQueue(
        f'{settings.QUEUE_PAYMENTS_NEW}.retry.{attempt}',
        durable=True,
        arguments={
            'x-message-ttl': int(get_retry_delay(attempt) * 1000),
            'x-dead-letter-exchange': payments_exchange.name,
            'x-dead-letter-routing-key': PAYMENTS_NEW_ROUTING_KEY,
        },
    )
    for attempt in range(1, settings.PAYMENT_MAX_ATTEMPTS)
)

BINDINGS: tuple[tuple[RabbitQueue, RabbitExchange], ...] = (
    (queue_payments_new, payments_exchange),
    (queue_payments_new_dlq, payments_dlx),
    *((queue, payments_retry_exchange) for queue in queues_payments_new_retry),
)


async def declare_topology(broker: 'RabbitBroker') -> None:
    """
    Идемпотентное объявление всех exchange, очередей и привязок.

    Вызывается и relay, и consumer при старте: события не теряются,
    даже если relay начал публикацию раньше, чем поднялся consumer.
    """
    for queue, exchange in BINDINGS:
        exchange_obj = await broker.declare_exchange(exchange)
        queue_obj = await broker.declare_queue(queue)
        await queue_obj.bind(exchange_obj, routing_key=queue.routing())
