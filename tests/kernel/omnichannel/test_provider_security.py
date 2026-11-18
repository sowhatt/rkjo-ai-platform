"""OMNI-011: reject forgery, unknown account, wrong bot and duplicate status identity."""
import hashlib
import hmac
import json

import pytest

from rkjo_kernel.omnichannel.inbound import (
    ChannelInboundGateway, InboundKind, InboundRoute,
)
from rkjo_kernel.omnichannel.provider_security import (
    ProviderAccount, ProviderWebhookVerifier, StaticProviderAccountRegistry,
)


class MemoryInbox:
    def __init__(self):
        self.events = {}
    def accept_once(self, event):
        key = (event.tenant_id, event.channel, event.channel_account_id, event.provider_event_id)
        if key in self.events:
            return False
        self.events[key] = event
        return True


@pytest.fixture
def accounts():
    return StaticProviderAccountRegistry([
        ProviderAccount("whatsapp", "phone-a", "tenant-a", "meta-secret-a"),
        ProviderAccount("whatsapp", "phone-b", "tenant-b", "meta-secret-b"),
        ProviderAccount("telegram", "bot-a", "tenant-a", "telegram-secret-a"),
        ProviderAccount("telegram", "bot-b", "tenant-b", "telegram-secret-b"),
    ])


def wa_body(phone="phone-a", *, status=False):
    item = ({"id": "out-1", "status": "delivered", "timestamp": "1700000001"}
            if status else {"id": "in-1", "text": {"body": "hi"}})
    value = {"metadata": {"phone_number_id": phone},
             "statuses" if status else "messages": [item]}
    return json.dumps({"entry": [{"changes": [{"value": value}]}]}).encode()


def wa_headers(body, secret="meta-secret-a"):
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": "sha256=" + signature}


def test_whatsapp_valid_hmac_resolves_trusted_tenant_and_deduplicates(accounts):
    inbox = MemoryInbox()
    gateway = ChannelInboundGateway(
        verifier=ProviderWebhookVerifier(accounts=accounts), inbox=inbox,
    )
    body = wa_body()
    assert gateway.receive(channel="whatsapp", body=body, headers=wa_headers(body)) == InboundRoute.PENDING_MESSAGE
    assert gateway.receive(channel="whatsapp", body=body, headers=wa_headers(body)) == InboundRoute.DUPLICATE
    event = next(iter(inbox.events.values()))
    assert event.tenant_id == "tenant-a"
    assert event.kind == InboundKind.USER_MESSAGE


def test_whatsapp_signature_forgery_does_not_write_inbox(accounts):
    inbox = MemoryInbox()
    gateway = ChannelInboundGateway(verifier=ProviderWebhookVerifier(accounts=accounts), inbox=inbox)
    body = wa_body()
    with pytest.raises(PermissionError):
        gateway.receive(channel="whatsapp", body=body, headers=wa_headers(body, "incorrect"))
    assert not inbox.events


def test_whatsapp_cross_tenant_phone_spoofing_rejected(accounts):
    verifier = ProviderWebhookVerifier(accounts=accounts)
    body = wa_body("phone-b")
    with pytest.raises(PermissionError):
        verifier.verify_and_normalize(channel="whatsapp", body=body, headers=wa_headers(body, "meta-secret-a"))
    assert verifier.verify_and_normalize(
        channel="whatsapp", body=body, headers=wa_headers(body, "meta-secret-b"),
    ).tenant_id == "tenant-b"


def test_whatsapp_unknown_account_rejected(accounts):
    body = wa_body("unknown")
    with pytest.raises(PermissionError, match="Unknown"):
        ProviderWebhookVerifier(accounts=accounts).verify_and_normalize(
            channel="whatsapp", body=body, headers=wa_headers(body),
        )


def test_whatsapp_status_receipt_is_not_inbound_message(accounts):
    body = wa_body(status=True)
    verifier = ProviderWebhookVerifier(accounts=accounts)
    result = verifier.verify_and_normalize(channel="whatsapp", body=body, headers=wa_headers(body))
    assert result.kind == InboundKind.DELIVERY_RECEIPT
    assert result.provider_event_id == "status:out-1:delivered:1700000001"


def test_whatsapp_batch_refused_pending_explicit_splitting(accounts):
    document = json.loads(wa_body())
    messages = document["entry"][0]["changes"][0]["value"]["messages"]
    messages.append({"id": "in-2"})
    body = json.dumps(document).encode()
    with pytest.raises(ValueError, match="batches"):
        ProviderWebhookVerifier(accounts=accounts).verify_and_normalize(
            channel="whatsapp", body=body, headers=wa_headers(body),
        )


def test_telegram_trusted_endpoint_and_secret(accounts):
    verifier = ProviderWebhookVerifier(accounts=accounts, telegram_endpoint_account_id="bot-a")
    body = json.dumps({"update_id": 123, "message": {"text": "hi"}}).encode()
    event = verifier.verify_and_normalize(channel="telegram", body=body,
                                          headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret-a"})
    assert event.tenant_id == "tenant-a"
    assert event.provider_event_id == "123"
    with pytest.raises(PermissionError):
        verifier.verify_and_normalize(channel="telegram", body=body,
                                      headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret-b"})


def test_telegram_requires_trusted_bot_binding(accounts):
    verifier = ProviderWebhookVerifier(accounts=accounts)
    with pytest.raises(PermissionError, match="not bound"):
        verifier.verify_and_normalize(channel="telegram", body=b'{"update_id":5}',
                                      headers={"x-telegram-bot-api-secret-token": "telegram-secret-a"})


def test_telegram_non_message_event_routes_to_ignored(accounts):
    gateway = ChannelInboundGateway(
        verifier=ProviderWebhookVerifier(accounts=accounts, telegram_endpoint_account_id="bot-a"),
        inbox=MemoryInbox(),
    )
    assert gateway.receive(
        channel="telegram", body=b'{"update_id":6,"edited_message":{"text":"hi"}}',
        headers={"x-telegram-bot-api-secret-token": "telegram-secret-a"},
    ) == InboundRoute.IGNORED
