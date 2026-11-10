from dataclasses import replace
from datetime import datetime, timezone

import pytest

from rkjo_kernel.multimodal.notifications import (
    Notification, NotificationDeliveryWorker, NotificationStatus, RetryPolicy,
)


def test_retry_backoff_and_terminal_failure():
    policy = RetryPolicy(max_attempts=2, initial_delay_seconds=5)
    now = datetime(2026, 10, 8, tzinfo=timezone.utc)
    first = Notification("n", "t", "j", "whatsapp", "r", NotificationStatus.IN_FLIGHT,
                         attempts=1, lease_token="claim")
    retry = policy.on_failure(first, now=now, error="TimeoutError")
    assert retry.status == NotificationStatus.RETRY
    assert (retry.next_attempt_at - now).total_seconds() == 5
    assert retry.lease_token is None
    second = replace(first, attempts=2)
    exhausted = policy.on_failure(second, now=now, error="TimeoutError")
    assert exhausted.status == NotificationStatus.FAILED
    assert exhausted.next_attempt_at is None


def test_retry_refuses_unclaimed_notification():
    with pytest.raises(ValueError, match="claimed"):
        RetryPolicy().on_failure(
            Notification("n", "t", "j", "api", "r"),
            now=datetime.now(timezone.utc), error="error",
        )


def test_notification_requires_tenant_and_destination():
    with pytest.raises(ValueError, match="required"):
        Notification("n", "", "j", "api", "r")
    with pytest.raises(ValueError, match="required"):
        Notification("n", "t", "j", "api", "")


class Store:
    def __init__(self, claim):
        self.claim = claim
        self.sent = []
        self.failed = []

    def claim_due(self, *, now, lease_seconds):
        item, self.claim = self.claim, None
        return item

    def mark_sent(self, **kwargs):
        self.sent.append(kwargs)

    def mark_failed(self, **kwargs):
        self.failed.append(kwargs)


def test_worker_success_never_mutates_job():
    claimed = Notification("n", "t", "j", "api", "r", NotificationStatus.IN_FLIGHT,
                           attempts=1, lease_token="lease")
    store = Store((claimed, object()))
    class Adapter:
        def send(self, *, notification, message):
            assert notification.job_id == "j"
            return "provider-1"
    worker = NotificationDeliveryWorker(store=store, adapters={"api": Adapter()})
    assert worker.run_once() is True
    assert len(store.sent) == 1
    assert store.failed == []
    assert worker.run_once() is False


def test_worker_failure_records_retry_not_job_failure():
    claimed = Notification("n", "t", "j", "api", "r", NotificationStatus.IN_FLIGHT,
                           attempts=1, lease_token="lease")
    store = Store((claimed, object()))
    class Adapter:
        def send(self, *, notification, message):
            raise RuntimeError("transport down")
    worker = NotificationDeliveryWorker(store=store, adapters={"api": Adapter()})
    assert worker.run_once() is True
    assert store.sent == []
    assert store.failed[0]["error"] == "RuntimeError"
