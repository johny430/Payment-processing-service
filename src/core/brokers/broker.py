import logging

from faststream.rabbit import Channel, RabbitBroker

from src.core.settings import settings


def create_broker() -> RabbitBroker:
    """
    Создание брокера RabbitMQ.

    Publisher confirms + on_return_raises: публикация считается успешной, только если брокер
    подтвердил приём и сообщение было смаршрутизировано хотя бы в одну очередь.
    """
    return RabbitBroker(
        settings.rabbitmq_connection_url,
        default_channel=Channel(
            prefetch_count=settings.RABBITMQ_PREFETCH_COUNT,
            publisher_confirms=True,
            on_return_raises=True,
        ),
        logger=logging.getLogger(__name__),
        description='RabbitMQ сервиса процессинга платежей',
    )
