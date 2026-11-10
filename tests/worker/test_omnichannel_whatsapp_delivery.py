"""OMNI-016.2.3 — operational WhatsApp config and worker supervision tests."""
import json
from types import SimpleNamespace

import pytest

from rkjo_worker.omnichannel_whatsapp_delivery import (
    SupervisedWhatsAppDelivery, load_whatsapp_registry,
)


def meta_config(**overrides):
    item={
        "tenant_id":"tenant-a","channel_account_id":"account-a",
        "phone_number_id":"12345678901","token_env":"RKJO_META_TOKEN_A",
        "approved_templates":[{"id":"welcome","name":"welcome_fr","language_code":"fr"}],
    }
    item.update(overrides)
    return item


def env(entries=None):
    return {
        "RKJO_OMNI_WHATSAPP_ACCOUNTS_JSON": json.dumps(
            [meta_config()] if entries is None else entries
        ),
        "RKJO_META_TOKEN_A":"fake-token-a",
        "RKJO_META_TOKEN_B":"fake-token-b",
    }


def test_registry_loads_token_indirectly_and_tenant_scopes_templates():
    registry=load_whatsapp_registry(environ=env())
    account=registry.resolve(tenant_id="tenant-a",channel_account_id="account-a")
    assert account.access_token=="fake-token-a"
    assert registry.is_approved(
        tenant_id="tenant-a",channel_account_id="account-a",template_id="welcome"
    )
    assert registry.resolve_template(
        tenant_id="tenant-a",channel_account_id="account-a",
        template_id="welcome",
    ).name=="welcome_fr"
    assert not registry.is_approved(
        tenant_id="tenant-b",channel_account_id="account-a",template_id="welcome"
    )
    with pytest.raises(PermissionError):
        registry.resolve(tenant_id="tenant-b",channel_account_id="account-a")


@pytest.mark.parametrize("entries",[
    [meta_config(access_token="inline-secret")],
    [meta_config(token_env="PATH")],
    [meta_config(token_env="RKJO_META_TOKEN_UNDEFINED")],
    [meta_config(approved_templates={"id":"welcome"})],
    [meta_config(),meta_config()],
    [meta_config(approved_templates=[
        {"id":"welcome","name":"w","language_code":"fr"},
        {"id":"welcome","name":"w","language_code":"fr"},
    ])],
    [],
])
def test_invalid_account_or_inline_secret_fails_closed(entries):
    with pytest.raises(ValueError):
        load_whatsapp_registry(environ=env(entries))


def test_two_accounts_have_distinct_tokens_and_template_approval():
    entries=[
        meta_config(),
        meta_config(tenant_id="tenant-b",channel_account_id="account-b",
                    phone_number_id="9876543210",token_env="RKJO_META_TOKEN_B",
                    approved_templates=[]),
    ]
    registry=load_whatsapp_registry(environ=env(entries))
    a=registry.resolve(tenant_id="tenant-a",channel_account_id="account-a")
    b=registry.resolve(tenant_id="tenant-b",channel_account_id="account-b")
    assert a.access_token != b.access_token
    assert not registry.is_approved(
        tenant_id="tenant-b",channel_account_id="account-b",template_id="welcome"
    )


def test_missing_or_invalid_json_is_rejected():
    with pytest.raises(ValueError):
        load_whatsapp_registry(environ={})
    with pytest.raises(ValueError):
        load_whatsapp_registry(environ={"RKJO_OMNI_WHATSAPP_ACCOUNTS_JSON":"not-json"})


class Worker:
    def __init__(self, results=(), failure=None):
        self.results=iter(results)
        self.failure=failure
        self.calls=0

    def run_once(self, *, now):
        self.calls+=1
        if self.failure:
            raise self.failure
        return next(self.results,False)


def test_supervisor_bounded_batch_and_idle():
    worker=Worker([True,True,True,False])
    sup=SupervisedWhatsAppDelivery(worker=worker,batch_size=2)
    assert sup.run_cycle()==2
    assert sup.run_cycle()==1
    assert worker.calls==4


def test_supervisor_stop_prevents_new_sends():
    worker=Worker([True])
    sup=SupervisedWhatsAppDelivery(worker=worker)
    sup.stop()
    assert sup.run_cycle()==0
    assert worker.calls==0


def test_supervisor_suppresses_exception_detail_and_stops(monkeypatch):
    messages=[]
    monkeypatch.setattr(
        "rkjo_worker.omnichannel_whatsapp_delivery.logger.error",
        lambda msg: messages.append(msg),
    )
    worker=Worker(failure=RuntimeError("SECRET TOKEN MUST NOT BE PRINTED"))
    waits=[]
    sup=None
    def stop_after_sleep(seconds):
        waits.append(seconds)
        sup.stop()
    sup=SupervisedWhatsAppDelivery(
        worker=worker,poll_seconds=0.25,sleep_fn=stop_after_sleep,
    )
    sup.run()
    assert len(messages)==1
    assert "SECRET TOKEN" not in messages[0]
    assert waits==[0.25]


@pytest.mark.parametrize("options",[
    {"batch_size":0}, {"batch_size":1001},
    {"poll_seconds":0}, {"poll_seconds":61},
])
def test_supervisor_rejects_invalid_parameters(options):
    with pytest.raises(ValueError):
        SupervisedWhatsAppDelivery(worker=Worker(),**options)
