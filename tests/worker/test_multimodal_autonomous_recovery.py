"""Real RabbitMQ autonomous consumer recovery tests (opt-in).

Run only against dedicated test PostgreSQL and RabbitMQ endpoints.
Each run uses a uniquely named RabbitMQ queue. No production queues are consumed.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pika
import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from rkjo_kernel.config.settings import settings
from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.postgres_notifications import PostgreSQLNotificationStore
from rkjo_worker.multimodal_notification_consumer import (
    MultimodalNotificationConsumer, NotificationRegistrationHandler,
)


@pytest.fixture
def environment(monkeypatch):
    database_url = os.getenv("RKJO_TEST_DATABASE_URL")
    rabbit_url = os.getenv("RKJO_TEST_RABBITMQ_URL")
    if not database_url or not rabbit_url:
        pytest.skip("Set RKJO_TEST_DATABASE_URL and RKJO_TEST_RABBITMQ_URL.")
    if "test" not in conninfo_to_dict(database_url).get("dbname", "").lower():
        pytest.fail("Only dedicated PostgreSQL test databases are permitted.")
    token = uuid4().hex
    queue = f"rkjo.test.multimodal.consumer.{token}"
    monkeypatch.setattr(settings, "rabbitmq_url", rabbit_url)
    store = PostgreSQLNotificationStore(database_url)
    store.initialize_schema()
    connection = pika.BlockingConnection(pika.URLParameters(rabbit_url))
    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)
    yield store, rabbit_url, queue, channel
    channel.queue_delete(queue=queue)
    channel.queue_delete(queue=f"{queue}.dlq")
    connection.close()


def message():
    token = uuid4().hex
    return AgentMessage(
        message_id=f"notice-{token}", correlation_id=f"corr-{token}",
        source="rkjo.multimodal.job_events",
        target="rkjo.multimodal.channel_delivery",
        message_type="multimodal.notification.requested",
        payload={"job_id": f"job-{token}", "status": "completed", "event_version": 2},
        metadata={"tenant_id": f"tenant-{token}", "channel": "api",
                  "recipient_ref": f"opaque-{token}", "idempotency_key": token},
    )


def one_session(queue, handler, *, timeout=3.0, max_delivery_attempts=3):
    """Start real blocking RabbitMQ consumption; stop after first success or timeout."""
    bus = RabbitMQEventBus(max_delivery_attempts=max_delivery_attempts)
    processed = []

    def callback(msg):
        handler.handle(msg) if hasattr(handler, 'handle') else handler(msg)
        processed.append(msg.message_id)
        bus.channel.stop_consuming()

    # A callback failure causes the underlying RabbitMQ implementation
    # to republish before acknowledgement. The timed exit avoids a hung test.
    bus.connection.call_later(timeout, bus.channel.stop_consuming)
    try:
        bus.consume_agent_messages(queue_name=queue, callback=callback)
    finally:
        bus.close()
    return processed


def test_consumer_restart_redelivery_ack_and_deduplication(environment):
    store, _, queue, channel = environment
    item = message()
    body = item.model_dump_json().encode()
    channel.basic_publish(
        exchange="", routing_key=queue, body=body,
        properties=pika.BasicProperties(delivery_mode=2),
    )
    handler = NotificationRegistrationHandler(store)
    assert one_session(queue, handler) == [item.message_id]
    assert channel.queue_declare(queue=queue, passive=True).method.message_count == 0
    assert store.load(tenant_id=item.metadata["tenant_id"],
                      notification_id=item.message_id) is not None

    # Simulate broker redelivery after ACK loss with the original message bytes.
    channel.basic_publish(
        exchange="", routing_key=queue, body=body,
        properties=pika.BasicProperties(delivery_mode=2),
    )
    assert one_session(queue, handler) == [item.message_id]
    with psycopg.connect(store.database_url) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM multimodal_notifications WHERE notification_id=%s",
            (item.message_id,),
        ).fetchone()[0]
    assert count == 1
    assert channel.queue_declare(queue=queue, passive=True).method.message_count == 0


def test_consumer_failures_reach_dlq_without_registering_notice(environment):
    store, _, queue, channel = environment
    item = message()
    channel.basic_publish(
        exchange="", routing_key=queue,
        body=item.model_dump_json().encode(),
        properties=pika.BasicProperties(delivery_mode=2),
    )

    def broken(_msg):
        raise RuntimeError("simulated permanent storage outage")

    # The consumer must retry twice and then send the third failure to DLQ.
    # It will exit when its own timed stop fires after processing attempts.
    assert one_session(queue, broken, timeout=3.0) == []
    method, properties, body = channel.basic_get(queue=f"{queue}.dlq", auto_ack=False)
    assert method is not None, "Expected message in dead-letter queue"
    assert AgentMessage.model_validate_json(body).message_id == item.message_id
    assert properties.headers["x-rkjo-delivery-attempt"] == 3
    channel.basic_ack(delivery_tag=method.delivery_tag)
    assert store.load(tenant_id=item.metadata["tenant_id"],
                      notification_id=item.message_id) is None
