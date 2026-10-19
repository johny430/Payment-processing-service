from faststream.rabbit import TestApp, TestRabbitBroker

from src import consumer, outbox_relay
from src.core.brokers.topology import BINDINGS


async def test_consumer_app_declares_topology_on_startup():
    async with TestRabbitBroker(consumer.broker) as broker, TestApp(consumer.app):
        declared_queues = {call.args[0].name for call in broker.config.declarer.declare_queue.await_args_list}

    assert {queue.name for queue, _ in BINDINGS} <= declared_queues


async def test_outbox_relay_app_runs_relay_until_shutdown():
    async with TestRabbitBroker(outbox_relay.broker), TestApp(outbox_relay.app):
        is_running_inside = outbox_relay.relay.is_running

    assert is_running_inside is True
    assert outbox_relay.relay.is_running is False
