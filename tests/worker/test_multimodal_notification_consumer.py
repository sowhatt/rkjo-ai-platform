"""Consumer contracts; broker is replaced by a fake event bus."""
from __future__ import annotations

import pytest

from rkjo_worker.multimodal_notification_consumer import (
    MultimodalNotificationConsumer, NotificationRegistrationHandler,
)


class Store:
    def __init__(self):
        self.items = {}

    def register_once(self, message):
        self.items.setdefault(message.message_id, message)
        return self.items[message.message_id]


class Bus:
    def __init__(self, messages=(), fail=False):
        self.messages = messages
        self.fail = fail
        self.closed = False
        self.queue = None

    def consume_agent_messages(self, queue_name, callback):
        self.queue = queue_name
        if self.fail:
            raise ConnectionError("broker unavailable")
        for message in self.messages:
            callback(message)

    def close(self):
        self.closed = True


class Message:
    message_id = "n-1"


def test_registration_is_idempotent_and_uses_existing_queue():
    store = Store()
    bus = Bus([Message(), Message()])
    consumer = MultimodalNotificationConsumer(
        event_bus_factory=lambda: bus,
        handler=NotificationRegistrationHandler(store),
    )
    consumer.run()
    assert bus.queue == "rkjo.multimodal.notifications"
    assert list(store.items) == ["n-1"]
    assert bus.closed


def test_broker_failure_reconnects_without_losing_registration():
    store = Store()
    broken = Bus(fail=True)
    healthy = Bus([Message()])
    instances = iter([broken, healthy])
    delays = []
    consumer = MultimodalNotificationConsumer(
        event_bus_factory=lambda: next(instances),
        handler=NotificationRegistrationHandler(store),
        sleep_fn=delays.append,
    )
    consumer.run()
    assert delays == [1.0]
    assert broken.closed and healthy.closed
    assert list(store.items) == ["n-1"]


def test_invalid_configuration_rejected():
    with pytest.raises(ValueError):
        MultimodalNotificationConsumer(
            event_bus_factory=Bus,
            handler=NotificationRegistrationHandler(Store()),
            queue_name=" ",
        )
