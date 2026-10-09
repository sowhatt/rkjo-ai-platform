"""OMNI-010 gateway: verified-only ingress and durable deduplication."""
import os
from uuid import uuid4

import pytest

from rkjo_kernel.omnichannel.inbound import (
    ChannelInboundGateway, InboundKind, InboundRoute, VerifiedInbound,
)
from rkjo_kernel.omnichannel.postgres_inbox import PostgreSQLInboundInbox


class Verifier:
    def verify_and_normalize(self, *, channel, body, headers):
        if headers.get("verified") != "yes":
            raise PermissionError("Invalid webhook authentication.")
        return VerifiedInbound(
            channel=channel, channel_account_id="provider-account",
            provider_event_id=body.decode(),
            tenant_id=headers.get("tenant", "tenant-a"),
            kind=InboundKind(headers.get("kind", "user_message")),
            payload={"external_id": body.decode()},
        )


class MemoryInbox:
    def __init__(self):
        self.keys = set()

    def accept_once(self, event):
        key = (event.tenant_id, event.channel, event.channel_account_id, event.provider_event_id)
        if key in self.keys:
            return False
        self.keys.add(key)
        return True


def test_webhook_rejected_before_inbox_side_effect():
    store = MemoryInbox()
    gateway = ChannelInboundGateway(verifier=Verifier(), inbox=store)
    with pytest.raises(PermissionError):
        gateway.receive(channel="whatsapp", body=b"event1", headers={})
    assert not store.keys


def test_inbound_deduplication_is_tenant_scoped():
    gateway = ChannelInboundGateway(verifier=Verifier(), inbox=MemoryInbox())
    args = dict(channel="whatsapp", body=b"event1")
    assert gateway.receive(**args, headers={"verified": "yes"}) == InboundRoute.PENDING_MESSAGE
    assert gateway.receive(**args, headers={"verified": "yes"}) == InboundRoute.DUPLICATE
    assert gateway.receive(**args, headers={"verified": "yes", "tenant": "tenant-b"}) == InboundRoute.PENDING_MESSAGE


@pytest.mark.parametrize(("kind", "expected"), [
    ("user_message", InboundRoute.PENDING_MESSAGE),
    ("delivery_receipt", InboundRoute.PENDING_RECEIPT),
    ("ignored", InboundRoute.IGNORED),
])
def test_event_route_is_explicit_and_receipts_do_not_invoke_agent(kind, expected):
    gateway = ChannelInboundGateway(verifier=Verifier(), inbox=MemoryInbox())
    assert gateway.receive(
        channel="telegram", body=b"event2",
        headers={"verified": "yes", "kind": kind},
    ) == expected


def test_postgres_inbox_is_atomic_and_preserves_existing_payload():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL required.")
    from psycopg.conninfo import conninfo_to_dict
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Requires a dedicated test database.")
    inbox = PostgreSQLInboundInbox(url)
    inbox.initialize_schema()
    token = uuid4().hex
    event = VerifiedInbound(
        channel="whatsapp", channel_account_id=f"account-{token}",
        provider_event_id=f"message-{token}", tenant_id=f"tenant-{token}",
        kind=InboundKind.USER_MESSAGE, payload={"text": "hello"},
    )
    assert inbox.accept_once(event)
    assert not PostgreSQLInboundInbox(url).accept_once(event)
    with pytest.raises(ValueError, match="collides"):
        inbox.accept_once(VerifiedInbound(
            channel=event.channel, channel_account_id=event.channel_account_id,
            provider_event_id=event.provider_event_id, tenant_id=event.tenant_id,
            kind=InboundKind.USER_MESSAGE, payload={"text": "changed"},
        ))
    assert inbox.accept_once(VerifiedInbound(
        channel=event.channel, channel_account_id=event.channel_account_id,
        provider_event_id=event.provider_event_id, tenant_id=f"other-{token}",
        kind=InboundKind.USER_MESSAGE, payload={"text": "hello"},
    ))
