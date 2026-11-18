"""OMNI-016.2.2: integration of real PostgreSQL notification and receipt ledgers.

Meta HTTP remains a deterministic fake. These tests verify the existing
ownership guard and bounded provider-acceptance retry fencing end to end.
"""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.notifications import NotificationStatus
from rkjo_kernel.multimodal.postgres_notifications import PostgreSQLNotificationStore
from rkjo_kernel.omnichannel.conversation_router import PostgreSQLConversationRouter
from rkjo_kernel.omnichannel.contracts import ChannelResponse, ResponseKind, ResponseOrigin
from rkjo_kernel.omnichannel.delivery_ledger import PostgreSQLDeliveryLedger
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound
from rkjo_kernel.omnichannel.whatsapp_cloud import WhatsAppAccount, WhatsAppTemplate
from rkjo_kernel.omnichannel.whatsapp_runtime import (
    ConfiguredWhatsAppRegistry, build_whatsapp_delivery_worker,
)

NOW=datetime(2026,10,10,12,tzinfo=timezone.utc)


class Meta:
    def __init__(self, status=200, failure=None):
        self.calls=[]
        self.status=status
        self.failure=failure

    def post(self, **kwargs):
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return self.status,{"messages":[{"id":"wamid.RUNTIME001"}]}


def registry(*, approved=True):
    return ConfiguredWhatsAppRegistry(
        accounts={("tenant-a","phone-a"):WhatsAppAccount(
            "tenant-a","phone-a","12345678901","secret-token",
        )},
        approved_templates={
            ("tenant-a","phone-a","welcome"):WhatsAppTemplate("welcome_fr","fr")
        } if approved else {},
    )


@pytest.fixture
def database():
    url=os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL required")
    if "test" not in conninfo_to_dict(url).get("dbname","").lower():
        pytest.fail("Dedicated PostgreSQL test DB required")
    schema="rkjo_omni_whatsapp_"+uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "'+schema+'"')
    scoped=make_conninfo(url,options="-c search_path="+schema)
    try:
        router=PostgreSQLConversationRouter(scoped)
        router.initialize_schema()
        store=PostgreSQLNotificationStore(scoped)
        store.initialize_schema()
        ledger=PostgreSQLDeliveryLedger(scoped)
        ledger.initialize_schema()
        yield scoped,router,store,ledger
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "'+schema+'" CASCADE')


def route(router, *, at=NOW):
    event=VerifiedInbound(
        tenant_id="tenant-a",channel="whatsapp",
        channel_account_id="phone-a",provider_event_id="in-1",
        kind=InboundKind.USER_MESSAGE,
        payload={"event":{
            "id":"in-1","from":"33612345678",
            "timestamp":str(int(at.timestamp())),
            "text":{"body":"Salut"},
        }},
    )
    return router.route(event)


def register(store, routed, *, kind=ResponseKind.TEXT, origin=ResponseOrigin.AGENT,
             version=0, operator_id=None, template=None):
    response=ChannelResponse(
        notification_id="notify-wa-1",tenant_id="tenant-a",
        conversation_id=routed.conversation_id,channel="whatsapp",
        channel_account_id="phone-a",recipient_ref="33612345678",
        origin=origin,ownership_version=version,kind=kind,
        text="Bonjour" if kind==ResponseKind.TEXT else None,
        fallback_template_id=template,
    )
    message=AgentMessage(
        message_id="notify-wa-1",
        source="rkjo.multimodal.job_events",
        target="rkjo.multimodal.channel_delivery",
        message_type="multimodal.notification.requested",
        metadata={
            "tenant_id":"tenant-a", "channel":"whatsapp",
            "recipient_ref":"33612345678","operator_id":operator_id,
        },
        payload={
            "job_id":"job-wa-1",
            "omnichannel_response":response.model_dump(mode="json"),
        },
    )
    store.register_once(message)


def worker(database, transport, *, template_registry=None):
    return build_whatsapp_delivery_worker(
        database_url=database, registry=template_registry or registry(),
        transport=transport, now=lambda: NOW,
    )


def test_full_text_send_registers_meta_wamid_and_marks_notification_sent(database):
    db,router,store,ledger=database
    routed=route(router,at=NOW-timedelta(minutes=2))
    register(store,routed)
    meta=Meta()
    assert worker(db,meta).run_once(now=NOW)
    assert len(meta.calls)==1
    assert meta.calls[0]["payload"]["type"]=="text"
    assert store.load(tenant_id="tenant-a",notification_id="notify-wa-1").status==NotificationStatus.SENT
    state=ledger.load(tenant_id="tenant-a",notification_id="notify-wa-1")
    assert state.provider_message_id=="wamid.RUNTIME001"
    assert state.channel_account_id=="phone-a"
    assert not worker(db,meta).run_once(now=NOW)
    assert len(meta.calls)==1


def test_expired_window_is_terminal_with_no_provider_call(database):
    db,router,store,ledger=database
    routed=route(router,at=NOW-timedelta(days=2))
    register(store,routed)
    meta=Meta()
    assert worker(db,meta).run_once(now=NOW)
    state=store.load(tenant_id="tenant-a",notification_id="notify-wa-1")
    assert state.status==NotificationStatus.FAILED
    assert state.last_error=="PermanentDeliveryRejection"
    assert meta.calls==[]
    assert ledger.load(tenant_id="tenant-a",notification_id="notify-wa-1") is None


def test_approved_template_can_send_outside_24h_as_meta_template(database):
    db,router,store,ledger=database
    routed=route(router,at=NOW-timedelta(days=3))
    register(store,routed,kind=ResponseKind.TEMPLATE,template="welcome")
    meta=Meta()
    assert worker(db,meta).run_once(now=NOW)
    assert meta.calls[0]["payload"]["type"]=="template"
    assert meta.calls[0]["payload"]["template"]["name"]=="welcome_fr"
    assert store.load(tenant_id="tenant-a",notification_id="notify-wa-1").status==NotificationStatus.SENT


def test_unapproved_template_is_denied_before_meta(database):
    db,router,store,ledger=database
    routed=route(router,at=NOW-timedelta(days=3))
    register(store,routed,kind=ResponseKind.TEMPLATE,template="welcome")
    meta=Meta()
    assert worker(db,meta,template_registry=registry(approved=False)).run_once(now=NOW)
    assert meta.calls==[]
    assert store.load(tenant_id="tenant-a",notification_id="notify-wa-1").last_error=="PermanentDeliveryRejection"


def test_agent_reply_is_fenced_after_human_takeover(database):
    db,router,store,ledger=database
    routed=route(router,at=NOW-timedelta(minutes=2))
    register(store,routed)
    router.transfer(
        tenant_id="tenant-a",conversation_id=routed.conversation_id,
        expected_version=0,operator_id="operator-a",
    )
    meta=Meta()
    assert worker(db,meta).run_once(now=NOW)
    assert meta.calls==[]
    assert store.load(tenant_id="tenant-a",notification_id="notify-wa-1").last_error=="ObsoleteConversationResponse"


def test_http_429_retries_are_fenced_as_uncertain_no_second_send(database):
    db,router,store,ledger=database
    routed=route(router,at=NOW-timedelta(minutes=2))
    register(store,routed)
    meta=Meta(status=429)
    assert worker(db,meta).run_once(now=NOW)
    assert len(meta.calls)==1
    assert worker(db,meta).run_once(now=NOW+timedelta(minutes=2)) is False
    assert len(meta.calls)==1
    state=store.load(tenant_id="tenant-a",notification_id="notify-wa-1")
    assert state.status==NotificationStatus.FAILED
    assert state.last_error=="UncertainProviderAcceptance"


def test_registry_never_falls_back_between_tenants():
    accounts=registry()
    with pytest.raises(PermissionError):
        accounts.resolve(tenant_id="tenant-b",channel_account_id="phone-a")
    assert not accounts.is_approved(
        tenant_id="tenant-b",channel_account_id="phone-a",template_id="welcome",
    )
    with pytest.raises(PermissionError):
        accounts.resolve_template(
            tenant_id="tenant-a",channel_account_id="other",template_id="welcome",
        )
