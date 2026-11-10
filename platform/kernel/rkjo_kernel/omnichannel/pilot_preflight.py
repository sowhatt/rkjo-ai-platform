"""OMNI-016.2.4: read-only WhatsApp pilot preflight.

No provider calls, no secret values, no outbound messages.
Inspect only the requested tenant's account metadata and existing queue state.
An operator must explicitly enable a real Meta pilot after preflight.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from rkjo_kernel.omnichannel.operations import PostgreSQLOmnichannelOperations
from rkjo_kernel.omnichannel.whatsapp_runtime import ConfiguredWhatsAppRegistry


@dataclass(frozen=True, slots=True)
class WhatsAppPilotPreflight:
    tenant_id: str
    accounts_configured: int
    templates_configured: int
    pending_outbound: int
    failed_outbound: int
    uncertain_outbound: int
    provider_confirmed_uncommitted: int
    sent_without_binding: int
    ready_for_controlled_test: bool
    blockers: tuple[str, ...]


class WhatsAppPilotPreflightService:
    """Conservative gate; never claims that Meta credentials or templates
    are valid at the provider. The result is only local operational readiness.
    """

    def __init__(self, *, registry: ConfiguredWhatsAppRegistry,
                 operations: PostgreSQLOmnichannelOperations):
        self.registry = registry
        self.operations = operations

    def check(self, *, tenant_id: str, now: datetime | None = None) -> WhatsAppPilotPreflight:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("Tenant identity required.")
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Timezone-aware clock required.")
        account_keys = [key for key in self.registry.accounts if key[0] == tenant_id]
        templates = sum(
            1 for key in self.registry.approved_templates if key[0] == tenant_id
        )
        snapshot = self.operations.snapshot(tenant_id=tenant_id, now=now)
        blockers: list[str] = []
        if not account_keys:
            blockers.append("No WhatsApp account configured for tenant.")
        if snapshot.uncertain_outbound:
            blockers.append("Uncertain outbound deliveries require reconciliation.")
        if snapshot.provider_confirmed_uncommitted:
            blockers.append("Provider-accepted messages require ledger reconciliation.")
        if snapshot.sent_without_binding:
            blockers.append("Sent notifications lack provider ledger bindings.")
        if snapshot.outbound.expired_leases:
            blockers.append("Expired delivery leases require operator review.")
        if snapshot.outbound.failed:
            blockers.append("Failed outbound notifications require operator review.")
        return WhatsAppPilotPreflight(
            tenant_id=tenant_id, accounts_configured=len(account_keys),
            templates_configured=templates,
            pending_outbound=snapshot.outbound.pending,
            failed_outbound=snapshot.outbound.failed,
            uncertain_outbound=snapshot.uncertain_outbound,
            provider_confirmed_uncommitted=snapshot.provider_confirmed_uncommitted,
            sent_without_binding=snapshot.sent_without_binding,
            ready_for_controlled_test=not blockers,
            blockers=tuple(blockers),
        )
