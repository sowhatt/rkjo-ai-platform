"""Delivery state machine and ports for channel notifications."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Protocol

from rkjo_kernel.messages.agent_message import AgentMessage


class NotificationStatus(str, Enum):
    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    SENT = "sent"
    RETRY = "retry"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Notification:
    notification_id: str
    tenant_id: str
    job_id: str
    channel: str
    recipient_ref: str
    status: NotificationStatus = NotificationStatus.PENDING
    attempts: int = 0
    next_attempt_at: datetime | None = None
    lease_token: str | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        if not all((self.notification_id.strip(), self.tenant_id.strip(),
                    self.job_id.strip(), self.channel.strip(), self.recipient_ref.strip())):
            raise ValueError("Notification identity and destination are required.")
        if self.attempts < 0:
            raise ValueError("Notification attempts cannot be negative.")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 4
    initial_delay_seconds: int = 5
    max_delay_seconds: int = 300

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.initial_delay_seconds <= 0 or self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError("Invalid notification retry policy.")

    def on_failure(self, notification: Notification, *, now: datetime, error: str) -> Notification:
        if notification.status != NotificationStatus.IN_FLIGHT or notification.lease_token is None:
            raise ValueError("Notification must be claimed before failure.")
        if notification.attempts >= self.max_attempts:
            return replace(notification, status=NotificationStatus.FAILED, lease_token=None, last_error=error,
                           next_attempt_at=None)
        seconds = min(self.max_delay_seconds, self.initial_delay_seconds * (2 ** (notification.attempts - 1)))
        return replace(notification, status=NotificationStatus.RETRY, lease_token=None,
                       next_attempt_at=now + timedelta(seconds=seconds), last_error=error)


class ChannelDeliveryPort(Protocol):
    def send(self, *, notification: Notification, message: AgentMessage) -> str: ...
    # Provider must support an idempotency key (notification_id), or at-least-once
    # delivery can yield duplicates after a crash following provider acceptance.


class NotificationStorePort(Protocol):
    def register_once(self, message: AgentMessage) -> Notification: ...
    def claim_due(self, *, now: datetime, lease_seconds: int) -> tuple[Notification, AgentMessage] | None: ...
    def mark_sent(self, *, notification_id: str, tenant_id: str, lease_token: str, provider_ref: str) -> None: ...
    def mark_failed(self, *, notification_id: str, tenant_id: str, lease_token: str,
                    now: datetime, error: str, policy: RetryPolicy) -> None: ...


class NotificationDeliveryWorker:
    """One poll iteration; external supervision controls worker scheduling."""

    def __init__(self, *, store: NotificationStorePort, adapters: dict[str, ChannelDeliveryPort],
                 retry_policy: RetryPolicy | None = None, lease_seconds: int = 60) -> None:
        if lease_seconds <= 0:
            raise ValueError("Lease must be positive.")
        self.store = store
        self.adapters = adapters
        self.retry_policy = retry_policy or RetryPolicy()
        self.lease_seconds = lease_seconds

    def run_once(self, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        claim = self.store.claim_due(now=now, lease_seconds=self.lease_seconds)
        if claim is None:
            return False
        notification, message = claim
        try:
            adapter = self.adapters[notification.channel]
            provider_ref = adapter.send(notification=notification, message=message)
            if not provider_ref:
                raise ValueError("Channel adapter returned no provider reference.")
        except Exception as exc:
            self.store.mark_failed(
                notification_id=notification.notification_id, tenant_id=notification.tenant_id,
                lease_token=notification.lease_token or "", now=now,
                error=type(exc).__name__, policy=self.retry_policy,
            )
        else:
            self.store.mark_sent(
                notification_id=notification.notification_id, tenant_id=notification.tenant_id,
                lease_token=notification.lease_token or "", provider_ref=provider_ref,
            )
        return True
