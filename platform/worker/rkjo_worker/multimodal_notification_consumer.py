"""RabbitMQ registration consumer for durable multimodal notifications.

Consumes requests only: network delivery is performed by an independent
NotificationDeliveryWorker polling PostgreSQL, never inside the broker callback.
"""
from __future__ import annotations

import os
import signal
import time
from collections.abc import Callable

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.postgres_notifications import PostgreSQLNotificationStore
from rkjo_kernel.logging.logger import get_logger


logger = get_logger(__name__)
DEFAULT_QUEUE = "rkjo.multimodal.notifications"


class NotificationRegistrationHandler:
    def __init__(self, store: PostgreSQLNotificationStore) -> None:
        self.store = store

    def handle(self, message: AgentMessage) -> None:
        # register_once commits before returning. If broker ACK is lost,
        # redelivery is safe because notification_id is unique.
        self.store.register_once(message)


class MultimodalNotificationConsumer:
    def __init__(
        self, *, event_bus_factory: Callable[[], EventBus],
        handler: NotificationRegistrationHandler,
        queue_name: str = DEFAULT_QUEUE,
        retry_initial_seconds: float = 1.0,
        retry_max_seconds: float = 30.0,
        sleep_fn=time.sleep,
    ) -> None:
        if not queue_name.strip() or retry_initial_seconds <= 0 or retry_max_seconds < retry_initial_seconds:
            raise ValueError("Invalid queue or retry configuration.")
        self.event_bus_factory = event_bus_factory
        self.handler = handler
        self.queue_name = queue_name
        self.retry_initial_seconds = retry_initial_seconds
        self.retry_max_seconds = retry_max_seconds
        self.sleep_fn = sleep_fn
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        delay = self.retry_initial_seconds
        while self._running:
            bus = None
            try:
                bus = self.event_bus_factory()
                bus.consume_agent_messages(
                    queue_name=self.queue_name,
                    callback=self.handler.handle,
                )
                return
            except KeyboardInterrupt:
                return
            except Exception:
                if not self._running:
                    return
                logger.exception("Multimodal notification consumer interrupted; reconnecting.")
                self.sleep_fn(delay)
                delay = min(self.retry_max_seconds, delay * 2)
            finally:
                if bus is not None:
                    try:
                        bus.close()
                    except Exception:
                        logger.exception("Unable to close multimodal RabbitMQ connection.")


def main() -> None:
    database_url = os.environ["RKJO_DATABASE_URL"]
    store = PostgreSQLNotificationStore(
        database_url, max_attempts=int(os.getenv("RKJO_NOTIFICATION_MAX_ATTEMPTS", "4")),
    )
    # Schema migrations belong to deployment/bootstrap, not each worker restart.
    consumer = MultimodalNotificationConsumer(
        event_bus_factory=RabbitMQEventBus,
        handler=NotificationRegistrationHandler(store),
        queue_name=os.getenv("RKJO_MULTIMODAL_NOTIFICATION_QUEUE", DEFAULT_QUEUE),
    )

    def stop(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    consumer.run()


if __name__ == "__main__":
    main()
