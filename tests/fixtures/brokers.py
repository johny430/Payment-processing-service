import pytest
from faststream.rabbit import TestRabbitBroker

from src.consumer import broker
from src.core.brokers.topology import BINDINGS, declare_topology


@pytest.fixture
async def rmq_broker():
    """Брокер в памяти: обработчики вызываются напрямую, без RabbitMQ"""
    async with TestRabbitBroker(broker) as test_broker:
        yield test_broker


@pytest.fixture
async def real_rmq_broker():
    """Настоящий RabbitMQ с запущенным consumer и пустыми очередями"""
    await broker.connect()
    await declare_topology(broker)
    for queue, _ in BINDINGS:
        queue_obj = await broker.declare_queue(queue)
        await queue_obj.purge()
    await broker.start()

    yield broker

    await broker.stop()
