"""OMNI-016.1 — supervised RabbitMQ dispatch of durable omnichannel routes.

PostgreSQL remains the source of truth. RabbitMQ publisher confirms precede
outbox completion. An ACK lost after publication can cause another publish:
AgentMessage.message_id is stable and MUST be deduplicated downstream.
"""
from __future__ import annotations

import os
import signal
import time
from collections.abc import Callable
from datetime import datetime, timezone

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.omnichannel.conversation_router import PostgreSQLConversationRouter
from rkjo_kernel.omnichannel.route_consumers import (
    PostgreSQLOperatorInbox,
    RKJOAgentRouteConsumer,
)
from rkjo_kernel.omnichannel.route_outbox import PostgreSQLRouteOutbox, RoutingDispatchWorker


logger = get_logger(__name__)


class RabbitMQOmnichannelDispatcher:
    """Owns a short-lived transport while processing bounded routing batches.

    Connections never cross threads. Recoverable broker failures are recorded
    by the durable routing worker, and therefore retry through its lease.
    """

    def __init__(
        self, *,
        database_url: str,
        bus_factory: Callable[[], EventBus],
        agent_name: str,
        queue_name: str,
        max_attempts: int = 4,
        lease_seconds: int = 30,
    ):
        if not database_url.strip() or not queue_name.strip() or not agent_name.strip():
            raise ValueError("Database, queue and target agent required.")
        if max_attempts <= 0 or lease_seconds <= 0:
            raise ValueError("Positive retry and lease parameters required.")
        self.database_url = database_url
        self.bus_factory = bus_factory
        self.agent_name = agent_name
        self.queue_name = queue_name
        self.max_attempts = max_attempts
        self.lease_seconds = lease_seconds

    def dispatch_batch(self, *, now: datetime, limit: int = 50) -> int:
        if now.tzinfo is None or now.utcoffset() is None or limit < 1:
            raise ValueError("Timezone-aware now and positive limit required.")
        bus = self.bus_factory()
        try:
            router = PostgreSQLConversationRouter(self.database_url)
            outbox = PostgreSQLRouteOutbox(
                self.database_url, max_attempts=self.max_attempts,
            )
            operator = PostgreSQLOperatorInbox(self.database_url)
            worker = RoutingDispatchWorker(
                store=outbox, conversations=router,
                agent=RKJOAgentRouteConsumer(
                    bus=bus, agent_name=self.agent_name,
                    queue_name=self.queue_name,
                ),
                operator=operator, lease_seconds=self.lease_seconds,
            )
            processed = 0
            for _ in range(limit):
                if not worker.run_once(now=now):
                    break
                processed += 1
            return processed
        finally:
            bus.close()


def main() -> None:
    dispatcher = RabbitMQOmnichannelDispatcher(
        database_url=os.environ["RKJO_DATABASE_URL"],
        bus_factory=RabbitMQEventBus,
        agent_name=os.environ["RKJO_OMNI_AGENT_NAME"],
        queue_name=os.getenv("RKJO_OMNI_AGENT_QUEUE", "rkjo.omnichannel.agent"),
        max_attempts=int(os.getenv("RKJO_OMNI_ROUTE_MAX_ATTEMPTS", "4")),
    )
    interval = float(os.getenv("RKJO_OMNI_DISPATCH_POLL_SECONDS", "1"))
    if interval <= 0:
        raise ValueError("Poll interval must be positive.")
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        try:
            dispatcher.dispatch_batch(now=datetime.now(timezone.utc))
        except Exception:
            logger.exception("Omnichannel dispatch batch interrupted.")
        if running:
            time.sleep(interval)


if __name__ == "__main__":
    main()
