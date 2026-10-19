"""Consumer платежей: faststream run src.consumer:app"""

import logging

from faststream import FastStream

from src.core.brokers.broker import create_broker
from src.core.brokers.topology import declare_topology
from src.core.database.di import engine
from src.core.settings.log import setup_logging
from src.payments.brokers import payments_rmq_router
from src.payments.di import webhook_http_client

setup_logging()

broker = create_broker()
broker.include_router(payments_rmq_router)

app = FastStream(broker, logger=logging.getLogger(__name__))


@app.on_startup
async def setup_topology() -> None:
    # Топология объявляется до старта подписчиков, чтобы DLX и retry-очереди существовали к первой ошибке
    await broker.connect()
    await declare_topology(broker)


@app.after_shutdown
async def close_resources() -> None:
    await webhook_http_client.aclose()
    await engine.dispose()
