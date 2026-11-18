"""OMNI-016.2 WhatsApp Cloud API contract tests; no live Meta credentials."""
import pytest

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.notifications import Notification
from rkjo_kernel.omnichannel.channel_policy import PermanentDeliveryRejection
from rkjo_kernel.omnichannel.contracts import ChannelResponse, ResponseKind, ResponseOrigin
from rkjo_kernel.omnichannel.whatsapp_cloud import (
    WhatsAppAccount, WhatsAppTemplate, WhatsAppCloudAPIAdapter, WhatsAppTransportError,
)


class Accounts:
    def __init__(self, *, wrong=False):
        self.wrong=wrong
    def resolve(self, *, tenant_id, channel_account_id):
        return WhatsAppAccount(
            tenant_id="other-tenant" if self.wrong else tenant_id,
            channel_account_id=channel_account_id,
            phone_number_id="12345678901",access_token="token-not-to-be-logged",
        )


class Templates:
    def __init__(self):
        self.calls=[]
    def resolve(self, *, tenant_id, channel_account_id, template_id):
        self.calls.append((tenant_id,channel_account_id,template_id))
        return WhatsAppTemplate(name="order_update",language_code="fr")


class Transport:
    def __init__(self, status=200, body=None, error=None):
        self.status=status
        self.body={"messages":[{"id":"wamid.ABC123"}]} if body is None else body
        self.error=error
        self.calls=[]
    def post(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.status,self.body


def pair(*, kind=ResponseKind.TEXT, template=None, tenant="t1", account="p1"):
    response=ChannelResponse(
        notification_id="n1",tenant_id=tenant,
        conversation_id="c1",channel="whatsapp",channel_account_id=account,
        recipient_ref="33612345678",origin=ResponseOrigin.AGENT,
        ownership_version=0,kind=kind,
        text="Bonjour" if kind == ResponseKind.TEXT else None,
        fallback_template_id=template,
    )
    notification=Notification(notification_id="n1",tenant_id="t1",
                              job_id="j1",channel="whatsapp",recipient_ref="33612345678")
    message=AgentMessage(
        source="rkjo.agent",target="rkjo.notify",
        metadata={"tenant_id":"t1"},
        payload={"omnichannel_response":response.model_dump(mode="json")},
    )
    return notification,message


def adapter(transport, *, accounts=None, templates=None):
    return WhatsAppCloudAPIAdapter(
        accounts=accounts or Accounts(),
        templates=templates or Templates(),
        transport=transport,graph_version="v23.0",
    )


def test_text_message_is_tenant_bound_and_serialized():
    transport=Transport()
    notification,message=pair()
    assert adapter(transport).send(notification=notification,message=message)=="wamid.ABC123"
    assert len(transport.calls)==1
    call=transport.calls[0]
    assert call["url"]=="https://graph.facebook.com/v23.0/12345678901/messages"
    assert call["token"]=="token-not-to-be-logged"
    assert call["payload"]=={
        "messaging_product":"whatsapp","recipient_type":"individual",
        "to":"33612345678","type":"text",
        "text":{"preview_url":False,"body":"Bonjour"},
    }


def test_template_is_actual_meta_template_payload_not_free_text():
    transport=Transport()
    templates=Templates()
    notification,message=pair(kind=ResponseKind.TEMPLATE,template="approved-template-1")
    assert adapter(transport,templates=templates).send(
        notification=notification,message=message)=="wamid.ABC123"
    assert templates.calls==[("t1","p1","approved-template-1")]
    assert transport.calls[0]["payload"]["type"]=="template"
    assert transport.calls[0]["payload"]["template"]=={
        "name":"order_update","language":{"code":"fr"},
    }
    assert "text" not in transport.calls[0]["payload"]


@pytest.mark.parametrize("overrides",[
    {"tenant":"other-tenant"},
    {"account":"other-phone"},
])
def test_cross_tenant_account_response_is_denied_by_registry(overrides):
    transport=Transport()
    notification,message=pair(**overrides)
    with pytest.raises(PermissionError):
        adapter(transport,accounts=Accounts(wrong=True)).send(
            notification=notification,message=message)
    assert not transport.calls


def test_notification_or_metadata_identity_mismatch_prevents_provider_call():
    transport=Transport()
    notification,message=pair()
    message.metadata["tenant_id"]="other-tenant"
    with pytest.raises(PermissionError):
        adapter(transport).send(notification=notification,message=message)
    assert transport.calls==[]


@pytest.mark.parametrize("kind,kwargs",[
    (ResponseKind.BUTTONS,{"text":"Choose","options":["Yes"]}),
    (ResponseKind.MEDIA,{"media_ref":"artifact-1"}),
])
def test_unimplemented_kinds_fail_closed(kind,kwargs):
    notification,message=pair()
    response=ChannelResponse(
        notification_id="n1",tenant_id="t1",conversation_id="c1",
        channel="whatsapp",channel_account_id="p1",
        recipient_ref="33612345678",origin=ResponseOrigin.AGENT,
        ownership_version=0,kind=kind,**kwargs,
    )
    message.payload["omnichannel_response"]=response.model_dump(mode="json")
    transport=Transport()
    with pytest.raises(PermanentDeliveryRejection):
        adapter(transport).send(notification=notification,message=message)
    assert transport.calls==[]


@pytest.mark.parametrize("status,body",[
    (429,{"error":{"code":4}}),
    (500,{"error":{"code":131000}}),
    (200,{"messages":[]}),
    (200,{"messages":[{"id":"invalid"}]}),
    (200,{"messages":[{"id":"wamid.1"},{"id":"wamid.2"}]}),
])
def test_provider_error_or_unclear_acceptance_never_fakes_success(status,body):
    transport=Transport(status=status,body=body)
    notification,message=pair()
    with pytest.raises(WhatsAppTransportError):
        adapter(transport).send(notification=notification,message=message)
    assert len(transport.calls)==1


def test_transport_timeout_preserves_uncertain_outcome():
    transport=Transport(error=TimeoutError("timed out"))
    notification,message=pair()
    with pytest.raises(WhatsAppTransportError):
        adapter(transport).send(notification=notification,message=message)


def test_invalid_account_and_graph_version_fail_fast():
    with pytest.raises(ValueError):
        WhatsAppAccount("t1","p1","not-numeric","token")
    with pytest.raises(ValueError):
        WhatsAppCloudAPIAdapter(accounts=Accounts(),templates=Templates(),
                                transport=Transport(),graph_version="../../secrets")
