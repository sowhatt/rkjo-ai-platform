"""OMNI-016.2.4: tenant-scoped, secret-free local pilot readiness tests."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from rkjo_kernel.omnichannel.pilot_preflight import WhatsAppPilotPreflightService
from rkjo_kernel.omnichannel.whatsapp_cloud import WhatsAppAccount, WhatsAppTemplate
from rkjo_kernel.omnichannel.whatsapp_runtime import ConfiguredWhatsAppRegistry


NOW=datetime(2026,10,10,12,tzinfo=timezone.utc)


class Operations:
    def __init__(self, **overrides):
        self.values=dict(pending=0,failed=0,expired_leases=0,uncertain_outbound=0,
                         provider_confirmed_uncommitted=0,sent_without_binding=0)
        self.values.update(overrides)
        self.calls=[]

    def snapshot(self, *, tenant_id, now):
        self.calls.append((tenant_id,now))
        return SimpleNamespace(
            outbound=SimpleNamespace(**{
                key:self.values[key] for key in ("pending","failed","expired_leases")
            }),
            uncertain_outbound=self.values["uncertain_outbound"],
            provider_confirmed_uncommitted=self.values["provider_confirmed_uncommitted"],
            sent_without_binding=self.values["sent_without_binding"],
        )


def registry():
    return ConfiguredWhatsAppRegistry(
        accounts={
            ("a","phone-a"):WhatsAppAccount("a","phone-a","12345678901","secret-a"),
            ("b","phone-b"):WhatsAppAccount("b","phone-b","98765432101","secret-b"),
        },
        approved_templates={
            ("a","phone-a","welcome"):WhatsAppTemplate("welcome_fr","fr"),
        },
    )


def test_ready_tenant_no_secret_exposure():
    ops=Operations()
    result=WhatsAppPilotPreflightService(
        registry=registry(),operations=ops,
    ).check(tenant_id="a",now=NOW)
    assert result.ready_for_controlled_test
    assert result.accounts_configured==1
    assert result.templates_configured==1
    assert result.blockers==()
    assert "secret-a" not in repr(result)
    assert ops.calls==[("a",NOW)]


def test_missing_account_fails_closed_without_exposing_other_tenants():
    result=WhatsAppPilotPreflightService(
        registry=registry(),operations=Operations(),
    ).check(tenant_id="unknown",now=NOW)
    assert result.ready_for_controlled_test is False
    assert result.accounts_configured==0
    assert result.templates_configured==0
    assert len(result.blockers)==1


@pytest.mark.parametrize("risk",[
    "failed","expired_leases","uncertain_outbound",
    "provider_confirmed_uncommitted","sent_without_binding",
])
def test_each_outbound_risk_blocks_pilot(risk):
    result=WhatsAppPilotPreflightService(
        registry=registry(),operations=Operations(**{risk:1}),
    ).check(tenant_id="a",now=NOW)
    assert result.ready_for_controlled_test is False
    assert result.blockers


def test_pending_is_visible_but_not_a_credential_claim():
    result=WhatsAppPilotPreflightService(
        registry=registry(),operations=Operations(pending=5),
    ).check(tenant_id="a",now=NOW)
    assert result.pending_outbound==5
    assert result.ready_for_controlled_test
    assert result.templates_configured==1


def test_unapproved_template_list_is_not_claimed_verified_by_meta():
    configured=ConfiguredWhatsAppRegistry(
        accounts={("a","phone-a"):WhatsAppAccount(
            "a","phone-a","12345678901","secret-a",
        )},
        approved_templates={},
    )
    result=WhatsAppPilotPreflightService(
        registry=configured,operations=Operations(),
    ).check(tenant_id="a",now=NOW)
    assert result.templates_configured==0
    assert result.ready_for_controlled_test


@pytest.mark.parametrize("bad_tenant",["","  ",None])
def test_invalid_tenant_rejected(bad_tenant):
    with pytest.raises(ValueError):
        WhatsAppPilotPreflightService(
            registry=registry(),operations=Operations(),
        ).check(tenant_id=bad_tenant,now=NOW)


def test_naive_clock_rejected():
    with pytest.raises(ValueError):
        WhatsAppPilotPreflightService(
            registry=registry(),operations=Operations(),
        ).check(tenant_id="a",now=NOW.replace(tzinfo=None))
