"""Outbox relay: faststream run src.outbox_relay:app"""

import logging

from faststream import FastStream

from src.core.brokers.broker import create_broker
from src.core.brokers.topology import declare_topology, payments_exchange
from src.core.database.di import AsyncSessionLocal, engine
from src.core.settings import settings
from src.core.settings.log import setup_logging
from src.outbox.publisher import RabbitEventPublisher
from src.outbox.relay import OutboxRelay

setup_logging()

broker = create_broker()
relay = OutboxRelay(
    session_factory=AsyncSessionLocal,
    publisher=RabbitEventPublisher(broker, payments_exchange),
    batch_size=settings.OUTBOX_BATCH_SIZE,
    poll_interval=settings.OUTBOX_POLL_INTERVAL,
)

app = FastStream(broker, logger=logging.getLogger(__name__))


@app.on_startup
async def setup_topology() -> None:
    # Очереди объявляются заранее: иначе до старта consumer сообщениям некуда было бы маршрутизироваться
    await broker.connect()
    await declare_topology(broker)


@app.after_startup
async def start_relay() -> None:
    relay.start()


@app.on_shutdown
async def stop_relay() -> None:
    await relay.stop()


@app.after_shutdown
async def close_resources() -> None:
    await engine.dispose()
