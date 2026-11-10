"""OMNI-015.1 wiring of existing RKJO omnichannel components.

Composition root for an isolated tenant-bound integration environment. The
agent EventBus and delivery provider remain injectable. No network provider
is configured or called implicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from rkjo_kernel.omnichannel.conversation_router import (
    ConversationRoutingHandler, PostgreSQLConversationRouter,
)
from rkjo_kernel.omnichannel.delivery_ledger import (
    DeliveryReceiptHandler, PostgreSQLDeliveryLedger,
)
from rkjo_kernel.omnichannel.inbound import ChannelInboundGateway
from rkjo_kernel.omnichannel.inbound_processor import (
    InboundProcessingWorker, PostgreSQLInboundProcessorStore,
)
from rkjo_kernel.omnichannel.postgres_inbox import PostgreSQLInboundInbox
from rkjo_kernel.omnichannel.route_consumers import PostgreSQLOperatorInbox
from rkjo_kernel.omnichannel.route_outbox import (
    PostgreSQLRouteOutbox, RouteConsumerPort, RoutingDispatchWorker,
)


@dataclass(slots=True)
class OmnichannelPipeline:
    gateway: ChannelInboundGateway
    inbound: InboundProcessingWorker
    routed: RoutingDispatchWorker
    conversations: PostgreSQLConversationRouter
    delivery: PostgreSQLDeliveryLedger
    operators: PostgreSQLOperatorInbox

    def drain(self, *, now: datetime, max_events: int = 100) -> tuple[int, int]:
        """Process bounded queues; always handle ingress before route dispatch.

        Do not consider this a scheduler. Production must run supervised workers.
        """
        if max_events <= 0:
            raise ValueError("Positive max_events required.")
        inbound_count = 0
        routed_count = 0
        for _ in range(max_events):
            if not self.inbound.run_once(now=now):
                break
            inbound_count += 1
        for _ in range(max_events):
            if not self.routed.run_once(now=now):
                break
            routed_count += 1
        return inbound_count, routed_count


def build_pipeline(
    *, database_url: str, verifier, agent: RouteConsumerPort,
    max_attempts: int = 4,
) -> OmnichannelPipeline:
    """Initialize shared PostgreSQL components and connect worker ports."""
    inbox = PostgreSQLInboundInbox(database_url)
    inbox.initialize_schema()
    inbound_store = PostgreSQLInboundProcessorStore(
        database_url, max_attempts=max_attempts,
    )
    inbound_store.initialize_schema()
    conversations = PostgreSQLConversationRouter(database_url)
    conversations.initialize_schema()
    route_store = PostgreSQLRouteOutbox(database_url, max_attempts=max_attempts)
    operators = PostgreSQLOperatorInbox(database_url)
    operators.initialize_schema()
    delivery = PostgreSQLDeliveryLedger(database_url)
    delivery.initialize_schema()
    return OmnichannelPipeline(
        gateway=ChannelInboundGateway(verifier=verifier, inbox=inbox),
        inbound=InboundProcessingWorker(
            store=inbound_store,
            user_messages=ConversationRoutingHandler(conversations),
            delivery_receipts=DeliveryReceiptHandler(delivery),
        ),
        routed=RoutingDispatchWorker(
            store=route_store, conversations=conversations,
            agent=agent, operator=operators,
        ),
        conversations=conversations,
        delivery=delivery,
        operators=operators,
    )
