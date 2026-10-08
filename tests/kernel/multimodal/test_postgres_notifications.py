"""Opt-in integration tests for real PostgreSQL notification leases."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.notifications import NotificationStatus, RetryPolicy
from rkjo_kernel.multimodal.postgres_notifications import PostgreSQLNotificationStore


@pytest.fixture
def store():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RKJO_TEST_DATABASE_URL to run PostgreSQL integration tests.")
    adapter = PostgreSQLNotificationStore(url, max_attempts=2)
    adapter.initialize_schema()
    return adapter


def new_message():
    suffix = uuid4().hex
    return AgentMessage(
        message_id=f"notification-{suffix}", correlation_id=f"corr-{suffix}",
        source="rkjo.multimodal.job_events",
        target="rkjo.multimodal.channel_delivery",
        message_type="multimodal.notification.requested",
        payload={"job_id": f"job-{suffix}", "status": "completed", "event_version": 2},
        metadata={"tenant_id": f"tenant-{suffix}", "channel": "whatsapp",
                  "recipient_ref": f"opaque-{suffix}", "mission_id": "m",
                  "trace_id": "t", "idempotency_key": suffix},
    )


def test_register_once_is_durable_and_tenant_isolated(store):
    message = new_message()
    first = store.register_once(message)
    assert store.register_once(message) == first
    assert first.status == NotificationStatus.PENDING
    assert store.load(tenant_id="wrong-tenant", notification_id=message.message_id) is None
    assert store.load(tenant_id=message.metadata["tenant_id"],
                      notification_id=message.message_id) == first
    different = message.model_copy(deep=True)
    different.payload["status"] = "failed"
    with pytest.raises(ValueError, match="conflicts"):
        store.register_once(different)


def test_concurrent_workers_cannot_claim_same_notification(store):
    message = new_message()
    store.register_once(message)
    now = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(
            lambda _: store.claim_due(now=now, lease_seconds=60), range(2),
        ))
    assert sum(item is not None for item in claims) == 1
    claimed, payload = next(item for item in claims if item is not None)
    assert claimed.attempts == 1
    assert payload.message_id == message.message_id
    store.mark_sent(notification_id=claimed.notification_id, tenant_id=claimed.tenant_id,
                    lease_token=claimed.lease_token, provider_ref="provider-a")
    assert store.load(tenant_id=claimed.tenant_id, notification_id=claimed.notification_id).status == NotificationStatus.SENT
    assert store.claim_due(now=now + timedelta(minutes=3), lease_seconds=60) is None


def test_retry_due_time_stale_token_and_crash_recovery(store):
    message = new_message()
    store.register_once(message)
    now = datetime.now(timezone.utc)
    first, _ = store.claim_due(now=now, lease_seconds=10)
    with pytest.raises(ValueError, match="Stale"):
        store.mark_sent(notification_id=first.notification_id, tenant_id="wrong",
                        lease_token=first.lease_token, provider_ref="provider")
    store.mark_failed(
        notification_id=first.notification_id, tenant_id=first.tenant_id,
        lease_token=first.lease_token, now=now, error="Timeout",
        policy=RetryPolicy(max_attempts=2, initial_delay_seconds=5),
    )
    assert store.claim_due(now=now + timedelta(seconds=4), lease_seconds=10) is None
    second, _ = store.claim_due(now=now + timedelta(seconds=5), lease_seconds=10)
    assert second.attempts == 2
    with pytest.raises(ValueError, match="Stale"):
        store.mark_sent(notification_id=first.notification_id, tenant_id=first.tenant_id,
                        lease_token=first.lease_token, provider_ref="too-late")
    assert store.claim_due(now=now + timedelta(seconds=16), lease_seconds=10) is None
    stored = store.load(tenant_id=first.tenant_id, notification_id=first.notification_id)
    assert stored.status == NotificationStatus.FAILED
    assert stored.last_error == "LeaseExpired"


def test_expired_first_lease_can_be_reclaimed_by_another_worker(store):
    message = new_message()
    store.register_once(message)
    now = datetime.now(timezone.utc)
    first, _ = store.claim_due(now=now, lease_seconds=10)
    assert store.claim_due(now=now + timedelta(seconds=9), lease_seconds=10) is None
    recovered, _ = store.claim_due(now=now + timedelta(seconds=11), lease_seconds=10)
    assert recovered.notification_id == first.notification_id
    assert recovered.lease_token != first.lease_token
    assert recovered.attempts == 2
    store.mark_sent(notification_id=recovered.notification_id, tenant_id=recovered.tenant_id,
                    lease_token=recovered.lease_token, provider_ref="provider-success")
    assert store.load(tenant_id=recovered.tenant_id,
                      notification_id=recovered.notification_id).status == NotificationStatus.SENT
