import typing as t

if t.TYPE_CHECKING:
    from faststream.rabbit import RabbitBroker, RabbitExchange

    from src.outbox.dtos import OutboxEventDTO


class EventPublisher(t.Protocol):
    """Публикация события outbox во внешний брокер"""

    async def publish(self, event: 'OutboxEventDTO') -> None: ...


class RabbitEventPublisher:
    """
    Публикация событий outbox в exchange RabbitMQ; event_type используется как routing key.

    Сообщение persistent, message_id = id события — по нему потребитель может отсеять дубли.
    Метод возвращает управление только после publisher confirm от брокера.
    """

    def __init__(self, broker: 'RabbitBroker', exchange: 'RabbitExchange') -> None:
        self.broker = broker
        self.exchange = exchange

    async def publish(self, event: 'OutboxEventDTO') -> None:
        await self.broker.publish(
            event.payload,
            exchange=self.exchange,
            routing_key=event.event_type,
            message_id=str(event.id),
            persist=True,
        )
