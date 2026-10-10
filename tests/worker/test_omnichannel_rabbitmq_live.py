"""Opt-in real RabbitMQ acceptance smoke test for OMNI-016.1.

Requires RKJO_TEST_RABBITMQ_URL and RKJO_TEST_DATABASE_URL. Uses an
isolated queue and schema; does not start the agent runtime.
"""
import os
from datetime import datetime, timezone
from uuid import uuid4

import pika
import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.omnichannel.conversation_router import PostgreSQLConversationRouter
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound
from rkjo_worker.omnichannel_dispatcher import RabbitMQOmnichannelDispatcher


@pytest.mark.integration
def test_postgres_outbox_publishes_persistent_message_to_real_broker(monkeypatch):
    db_url=os.getenv("RKJO_TEST_DATABASE_URL")
    broker_url=os.getenv("RKJO_TEST_RABBITMQ_URL")
    if not db_url or not broker_url:
        pytest.skip("Set dedicated RKJO_TEST_DATABASE_URL and RKJO_TEST_RABBITMQ_URL")
    if "test" not in conninfo_to_dict(db_url).get("dbname","").lower():
        pytest.fail("Dedicated PostgreSQL test database required")
    schema="rkjo_omni_broker_"+uuid4().hex
    queue="rkjo.omnichannel.integration."+uuid4().hex
    from rkjo_kernel.events import rabbitmq_event_bus
    monkeypatch.setattr(
        rabbitmq_event_bus, "settings",
        type("RabbitSettings",(),{"rabbitmq_url":broker_url})(),
    )
    with psycopg.connect(db_url) as conn:
        conn.execute('CREATE SCHEMA "'+schema+'"')
    scoped=make_conninfo(db_url,options="-c search_path="+schema)
    try:
        router=PostgreSQLConversationRouter(scoped)
        router.initialize_schema()
        event=VerifiedInbound(
            tenant_id="tenant-e2e",channel="whatsapp",
            channel_account_id="phone-e2e",
            provider_event_id="msg-e2e",kind=InboundKind.USER_MESSAGE,
            payload={"event":{"id":"msg-e2e","from":"customer-e2e",
                              "timestamp":"1700000001","text":{"body":"Hello"}}},
        )
        router.route(event)
        dispatcher=RabbitMQOmnichannelDispatcher(
            database_url=scoped,bus_factory=RabbitMQEventBus,
            agent_name="rkjo.omni.test",queue_name=queue,
        )
        assert dispatcher.dispatch_batch(now=datetime.now(timezone.utc))==1
        connection=pika.BlockingConnection(pika.URLParameters(broker_url))
        try:
            channel=connection.channel()
            method,properties,body=channel.basic_get(queue=queue,auto_ack=False)
            assert method is not None
            assert properties.delivery_mode==pika.DeliveryMode.Persistent
            message=AgentMessage.model_validate_json(body)
            assert message.message_type=="omnichannel.inbound.message"
            assert message.metadata["tenant_id"]=="tenant-e2e"
            assert properties.message_id==message.message_id
            channel.basic_ack(delivery_tag=method.delivery_tag)
            channel.queue_delete(queue=queue)
        finally:
            connection.close()
        with psycopg.connect(scoped) as conn:
            assert conn.execute("SELECT status FROM omni_route_outbox").fetchone()[0]=="processed"
    finally:
        with psycopg.connect(db_url) as conn:
            conn.execute('DROP SCHEMA "'+schema+'" CASCADE')
