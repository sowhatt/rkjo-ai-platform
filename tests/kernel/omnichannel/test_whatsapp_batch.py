"""OMNI-012: real PostgreSQL batch atomicity and signed multi-event parsing."""
import hashlib
import hmac
import json
import os
from uuid import uuid4

import pytest
from psycopg.conninfo import conninfo_to_dict

from rkjo_kernel.omnichannel.inbound import InboundKind, InboundRoute, VerifiedInbound
from rkjo_kernel.omnichannel.postgres_inbox import PostgreSQLInboundInbox
from rkjo_kernel.omnichannel.provider_security import ProviderAccount, StaticProviderAccountRegistry
from rkjo_kernel.omnichannel.whatsapp_batch import BatchInboundGateway, WhatsAppBatchVerifier


class MemoryBatchInbox:
    def __init__(self):
        self.events = {}
    def accept_batch(self, events):
        # Mimic transaction conflict detection before changes.
        copied = self.events.copy()
        results = []
        for e in events:
            key = (e.tenant_id, e.channel, e.channel_account_id, e.provider_event_id)
            if key in copied and copied[key] != e.payload:
                raise ValueError("Webhook event identity collides with different content.")
            new = key not in copied
            copied[key] = e.payload
            results.append(new)
        self.events = copied
        return results


def make_body(phone="phone-a", prefix="batch"):
    value = {
        "metadata": {"phone_number_id": phone},
        "messages": [
            {"id": prefix + "-in1", "text": {"body": "hello"}},
            {"id": prefix + "-in2", "text": {"body": "photo"}, "image": {"id": "media1"}},
        ],
        "statuses": [
            {"id": prefix + "-out1", "status": "sent", "timestamp": "1700000001"},
            {"id": prefix + "-out1", "status": "delivered", "timestamp": "1700000002"},
            {"id": prefix + "-out1", "status": "read", "timestamp": "1700000003"},
        ],
    }
    return json.dumps({"entry": [{"changes": [{"value": value}]}]}).encode()


def signature(body, secret="app-secret"):
    return {"X-Hub-Signature-256": "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}


def verifier():
    return WhatsAppBatchVerifier(accounts=StaticProviderAccountRegistry([
        ProviderAccount("whatsapp", "phone-a", "tenant-a", "app-secret"),
        ProviderAccount("whatsapp", "phone-b", "tenant-b", "another-secret"),
    ]))


def test_whatsapp_batch_routes_messages_and_all_delivery_receipts():
    inbox = MemoryBatchInbox()
    gateway = BatchInboundGateway(verifier=verifier(), inbox=inbox)
    body = make_body()
    result = gateway.receive_batch(channel="whatsapp", body=body, headers=signature(body))
    assert result == (InboundRoute.PENDING_MESSAGE,) * 2 + (InboundRoute.PENDING_RECEIPT,) * 3
    assert len(inbox.events) == 5
    assert gateway.receive_batch(channel="whatsapp", body=body, headers=signature(body)) == (
        InboundRoute.DUPLICATE,) * 5
    assert all(key[0] == "tenant-a" for key in inbox.events)
    assert {key[3] for key in inbox.events if key[3].startswith("status:")} == {
        "status:batch-out1:sent:1700000001",
        "status:batch-out1:delivered:1700000002",
        "status:batch-out1:read:1700000003",
    }


def test_whatsapp_batch_signature_failure_is_all_or_nothing():
    inbox = MemoryBatchInbox()
    gateway = BatchInboundGateway(verifier=verifier(), inbox=inbox)
    body = make_body()
    with pytest.raises(PermissionError):
        gateway.receive_batch(channel="whatsapp", body=body, headers=signature(body, "wrong-secret"))
    assert not inbox.events


def test_mixed_tenant_accounts_with_different_app_secrets_rejected():
    document = json.loads(make_body())
    document["entry"].append({"changes": [{"value": {
        "metadata": {"phone_number_id": "phone-b"},
        "messages": [{"id": "b-in1"}],
    }}]})
    body = json.dumps(document).encode()
    with pytest.raises(PermissionError, match="separate Meta app"):
        verifier().verify_and_normalize_batch(channel="whatsapp", body=body, headers=signature(body))


def test_malformed_later_event_causes_zero_persisted_events():
    inbox = MemoryBatchInbox()
    gateway = BatchInboundGateway(verifier=verifier(), inbox=inbox)
    document = json.loads(make_body())
    document["entry"][0]["changes"][0]["value"]["statuses"].append({"status": "read"})
    body = json.dumps(document).encode()
    with pytest.raises(ValueError, match="ID missing"):
        gateway.receive_batch(channel="whatsapp", body=body, headers=signature(body))
    assert not inbox.events


def test_max_event_count_is_enforced():
    v = WhatsAppBatchVerifier(accounts=verifier().accounts, max_events=2)
    body = make_body()
    with pytest.raises(ValueError, match="count exceeds"):
        v.verify_and_normalize_batch(channel="whatsapp", body=body, headers=signature(body))


def test_postgres_batch_transaction_rolls_back_on_conflicting_duplicate():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL required.")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Requires a dedicated test database.")
    store = PostgreSQLInboundInbox(url)
    store.initialize_schema()
    token = uuid4().hex
    def event(key, payload):
        return VerifiedInbound(
            channel="whatsapp", channel_account_id="phone-"+token,
            provider_event_id=key, tenant_id="tenant-"+token,
            kind=InboundKind.USER_MESSAGE, payload={"text": payload},
        )
    existing = event("one", "original")
    assert store.accept_batch([existing]) == [True]
    assert store.accept_batch([existing]) == [False]
    with pytest.raises(ValueError, match="collides"):
        store.accept_batch([event("new", "would-rollback"), event("one", "changed")])
    assert store.accept_batch([event("new", "would-rollback")]) == [True]
    assert store.accept_batch([event("new", "would-rollback")]) == [False]


def test_postgres_batch_multi_status_idempotent():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL required.")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Requires a dedicated test database.")
    store = PostgreSQLInboundInbox(url)
    store.initialize_schema()
    token = uuid4().hex
    body = make_body(prefix=token)
    events = verifier().verify_and_normalize_batch(channel="whatsapp", body=body, headers=signature(body))
    assert store.accept_batch(events) == [True] * 5
    assert store.accept_batch(events) == [False] * 5
