"""Opt-in PostgreSQL regression: queue-filtered publication does not touch other queues."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.outbox import OutboxMessage
from rkjo_kernel.workflow.outbox_publisher import OutboxPublisher
from rkjo_kernel.workflow.postgres_unit_of_work import (
    PostgreSQLTransactionalOutboxStore, PostgreSQLWorkflowUnitOfWork,
)


class RecordingBus:
    def __init__(self):
        self.sent = []

    def publish_agent_message(self, *, queue_name, message):
        self.sent.append((queue_name, message.message_id))


def test_postgres_scoped_publish_leaves_other_queue_pending():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL is required.")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Use a dedicated PostgreSQL test database.")
    PostgreSQLWorkflowUnitOfWork(url).initialize_schema()
    token = uuid4().hex
    other_queue = f"rkjo.test.unrelated.{token}"
    isolated_queue = f"rkjo.test.isolated.{token}"
    ids = []
    with psycopg.connect(url) as conn:
        outbox = PostgreSQLTransactionalOutboxStore(conn)
        for queue in (other_queue, isolated_queue):
            msg = AgentMessage(source="test", target="test", payload={})
            ids.append(msg.message_id)
            outbox.add(OutboxMessage(
                outbox_id=msg.message_id, queue_name=queue, message=msg,
                created_at=datetime.now(timezone.utc),
            ))
    try:
        bus = RecordingBus()
        publisher = OutboxPublisher(
            event_bus=bus, uow_factory=lambda: PostgreSQLWorkflowUnitOfWork(url),
            queue_name=isolated_queue,
        )
        assert publisher.publish_pending(limit=5) == 1
        assert bus.sent == [(isolated_queue, ids[1])]
        with psycopg.connect(url) as conn:
            rows = conn.execute(
                "SELECT outbox_id, published_at FROM workflow_outbox WHERE outbox_id = ANY(%s)",
                (ids,),
            ).fetchall()
        published = dict(rows)
        assert published[ids[0]] is None
        assert published[ids[1]] is not None
    finally:
        with psycopg.connect(url) as conn:
            conn.execute("DELETE FROM workflow_outbox WHERE outbox_id = ANY(%s)", (ids,))
