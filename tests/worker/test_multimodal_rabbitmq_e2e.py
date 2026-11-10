"""S31.2.4d opt-in PostgreSQL + real RabbitMQ integration smoke.

Requires BOTH RKJO_TEST_DATABASE_URL and RKJO_TEST_RABBITMQ_URL.
Uses isolated temporary queues. Delivery provider is a fake adapter.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pika
import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from rkjo_kernel.config.settings import settings
from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.multimodal.jobs import IngestionJob, JobStatus
from rkjo_kernel.multimodal.notifications import NotificationDeliveryWorker, NotificationStatus
from rkjo_kernel.multimodal.postgres_jobs import PostgreSQLIngestionJobAdapter
from rkjo_kernel.multimodal.postgres_notifications import PostgreSQLNotificationStore
from rkjo_kernel.workflow.outbox_publisher import OutboxPublisher
from rkjo_kernel.workflow.postgres_unit_of_work import PostgreSQLWorkflowUnitOfWork
from rkjo_worker.multimodal_job_event_consumer import build_job_event_consumer
from rkjo_worker.multimodal_notification_consumer import NotificationRegistrationHandler


def test_job_to_notification_with_real_broker(monkeypatch):
    db = os.getenv("RKJO_TEST_DATABASE_URL")
    rabbit = os.getenv("RKJO_TEST_RABBITMQ_URL")
    if not db or not rabbit:
        pytest.skip("Set both RKJO_TEST_DATABASE_URL and RKJO_TEST_RABBITMQ_URL.")
    from psycopg.conninfo import conninfo_to_dict
    if "test" not in conninfo_to_dict(db).get("dbname", "").lower():
        pytest.fail("E2E requires a dedicated PostgreSQL test database.")
    token = uuid4().hex
    job_queue = f"rkjo.test.multimodal.jobs.{token}"
    notify_queue = f"rkjo.test.multimodal.notifications.{token}"
    PostgreSQLWorkflowUnitOfWork(db).initialize_schema()
    jobs = PostgreSQLIngestionJobAdapter(db, event_queue=job_queue)
    jobs.initialize_schema()
    # Use a per-run schema for notification delivery: old test notifications
    # must not be visible to the unscoped production delivery worker.
    notification_schema = f"rkjo_e2e_notifications_{token}"
    with psycopg.connect(db) as db_conn:
        db_conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(notification_schema)))
    notification_db = make_conninfo(
        db, options=f"-c search_path={notification_schema},public",
    )
    notifications = PostgreSQLNotificationStore(notification_db)
    notifications.initialize_schema()
    monkeypatch.setattr(settings, "rabbitmq_url", rabbit)
    connection = pika.BlockingConnection(pika.URLParameters(rabbit))
    bus = None
    try:
        channel = connection.channel()
        for queue in (job_queue, notify_queue):
            channel.queue_declare(queue=queue, durable=True)
        job = IngestionJob(
            job_id=f"job-{token}", tenant_id=f"tenant-{token}",
            idempotency_key=token, channel="api", recipient_ref=f"opaque-{token}",
            correlation_id=f"corr-{token}", mission_id="m", trace_id="t",
        )
        jobs.accept_once(job)
        jobs.transition_and_enqueue_event(
            tenant_id=job.tenant_id, job_id=job.job_id, expected_version=0,
            new_status=JobStatus.STARTED, event_id=f"started-{token}",
        )
        jobs.transition_and_enqueue_event(
            tenant_id=job.tenant_id, job_id=job.job_id, expected_version=1,
            new_status=JobStatus.COMPLETED, event_id=f"completed-{token}",
        )
        bus = RabbitMQEventBus()
        publisher = OutboxPublisher(
            event_bus=bus, uow_factory=lambda: PostgreSQLWorkflowUnitOfWork(db),
            queue_name=job_queue,
        )
        assert publisher.publish_pending(limit=3) == 3
        consumer = build_job_event_consumer(
            database_url=db, job_queue=job_queue, notification_queue=notify_queue,
        )
        count = 0
        while True:
            method, _, body = channel.basic_get(queue=job_queue, auto_ack=False)
            if method is None:
                break
            from rkjo_kernel.messages.agent_message import AgentMessage
            consumer.handler.handle(AgentMessage.model_validate_json(body))
            channel.basic_ack(delivery_tag=method.delivery_tag)
            count += 1
        assert count == 3
        # Already-processed event is safe on broker redelivery.
        # A second publication cycle delivers the committed notification outbox.
        notification_publisher = OutboxPublisher(
            event_bus=bus, uow_factory=lambda: PostgreSQLWorkflowUnitOfWork(db),
            queue_name=notify_queue,
        )
        assert notification_publisher.publish_pending(limit=3) == 3
        registrar = NotificationRegistrationHandler(notifications)
        terminal_notification_id = f"multimodal:notify:{job.tenant_id}:{job.job_id}:2"
        received = 0
        terminal_message = None
        while True:
            method, _, body = channel.basic_get(queue=notify_queue, auto_ack=False)
            if method is None:
                break
            from rkjo_kernel.messages.agent_message import AgentMessage
            message = AgentMessage.model_validate_json(body)
            registrar.handle(message)
            registrar.handle(message)
            if message.message_id == terminal_notification_id:
                terminal_message = message
            channel.basic_ack(delivery_tag=method.delivery_tag)
            received += 1
        assert received == 3
        assert terminal_message is not None
        assert notifications.load(
            tenant_id=job.tenant_id, notification_id=terminal_notification_id,
        ).status == NotificationStatus.PENDING

        class FakeChannel:
            def __init__(self):
                self.ids = []
            def send(self, *, notification, message):
                self.ids.append(notification.notification_id)
                return f"provider-{notification.notification_id}"

        fake = FakeChannel()
        worker = NotificationDeliveryWorker(store=notifications, adapters={"api": fake})
        for _ in range(3):
            assert worker.run_once(now=datetime.now(timezone.utc))
        assert not worker.run_once(now=datetime.now(timezone.utc))
        assert notifications.load(
            tenant_id=job.tenant_id, notification_id=terminal_notification_id,
        ).status == NotificationStatus.SENT
        assert jobs.load(tenant_id=job.tenant_id, job_id=job.job_id).status == JobStatus.COMPLETED
        assert len(fake.ids) == 3
    finally:
        if bus is not None:
            bus.close()
        for queue in (job_queue, notify_queue):
            connection.channel().queue_delete(queue=queue)
        connection.close()
        with psycopg.connect(db) as db_conn:
            db_conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(
                sql.Identifier(notification_schema),
            ))
