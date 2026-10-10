"""OMNI-016.2.2: fail-closed production wiring for WhatsApp outbound.

Credential values are injected from a secret manager at deployment; NEVER
store Meta tokens in the Omnichannel PostgreSQL tables or event payloads.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping

import psycopg

from rkjo_kernel.multimodal.notifications import NotificationDeliveryWorker, RetryPolicy
from rkjo_kernel.multimodal.postgres_notifications import PostgreSQLNotificationStore
from rkjo_kernel.omnichannel.channel_policy import WhatsAppWindowPolicy
from rkjo_kernel.omnichannel.contracts import ChannelResponse
from rkjo_kernel.omnichannel.delivery_ledger import PostgreSQLDeliveryLedger
from rkjo_kernel.omnichannel.guarded_delivery import OwnershipFencedChannelAdapter
from rkjo_kernel.omnichannel.whatsapp_cloud import (
    WhatsAppAccount, WhatsAppCloudAPIAdapter, WhatsAppTemplate,
    WhatsAppHTTPTransport,
)


class ConfiguredWhatsAppRegistry:
    """Explicit tenant/account binding; no global token fallback.

    Approved templates are scoped to exactly the same tenant/account key.
    Configurations should be sourced from a secret manager, not committed.
    """

    def __init__(
        self, *,
        accounts: Mapping[tuple[str, str], WhatsAppAccount],
        approved_templates: Mapping[tuple[str, str, str], WhatsAppTemplate],
    ):
        self.accounts = dict(accounts)
        self.approved_templates = dict(approved_templates)
        for (tenant, account), item in self.accounts.items():
            if item.tenant_id != tenant or item.channel_account_id != account:
                raise ValueError("WhatsApp account registry key mismatch.")
        for (tenant, account, template_id), template in self.approved_templates.items():
            if not all((tenant, account, template_id, template.name, template.language_code)):
                raise ValueError("Invalid approved template registry key.")
            if (tenant, account) not in self.accounts:
                raise ValueError("Approved template has no bound account.")

    def resolve(self, *, tenant_id: str, channel_account_id: str) -> WhatsAppAccount:
        try:
            return self.accounts[(tenant_id, channel_account_id)]
        except KeyError:
            raise PermissionError("Unregistered WhatsApp tenant/account.") from None

    def is_approved(
        self, *, tenant_id: str, channel_account_id: str, template_id: str,
    ) -> bool:
        return (tenant_id, channel_account_id, template_id) in self.approved_templates

    def resolve_template(
        self, *, tenant_id: str, channel_account_id: str, template_id: str,
    ) -> WhatsAppTemplate:
        try:
            return self.approved_templates[(tenant_id, channel_account_id, template_id)]
        except KeyError:
            raise PermissionError("WhatsApp template not approved for account.") from None


class TemplateResolver:
    def __init__(self, registry: ConfiguredWhatsAppRegistry):
        self.registry = registry

    def resolve(
        self, *, tenant_id: str, channel_account_id: str, template_id: str,
    ) -> WhatsAppTemplate:
        return self.registry.resolve_template(
            tenant_id=tenant_id, channel_account_id=channel_account_id,
            template_id=template_id,
        )


class PostgreSQLVerifiedInboundClock:
    """Only the durable, authenticated conversation state opens the 24h window."""

    def __init__(self, database_url: str):
        if not database_url or not database_url.strip():
            raise ValueError("Database URL required.")
        self.database_url = database_url

    def __call__(self, response: ChannelResponse) -> datetime | None:
        with psycopg.connect(self.database_url) as conn:
            row = conn.execute("""
                SELECT last_inbound_at FROM omni_conversations
                WHERE tenant_id=%s AND conversation_id=%s
                  AND origin_channel='whatsapp'
            """, (response.tenant_id, response.conversation_id)).fetchone()
        return row[0] if row else None


def build_whatsapp_delivery_worker(
    *, database_url: str, registry: ConfiguredWhatsAppRegistry,
    transport: WhatsAppHTTPTransport | None = None,
    graph_version: str = "v23.0", max_attempts: int = 4,
    now=None,
) -> NotificationDeliveryWorker:
    """Compose existing durable worker, ownership guard, Meta port and ledger.

    Schema initialization is deliberately a deployment responsibility.
    A transient/ambiguous Meta outcome must not be replayed: PostgreSQL
    claim_due fences retries for the omnichannel_response contract.
    """
    store = PostgreSQLNotificationStore(database_url, max_attempts=max_attempts)
    ledger = PostgreSQLDeliveryLedger(database_url)
    policy = WhatsAppWindowPolicy(
        last_inbound=PostgreSQLVerifiedInboundClock(database_url),
        templates=registry, now=now,
    )
    provider = WhatsAppCloudAPIAdapter(
        accounts=registry, templates=TemplateResolver(registry),
        transport=transport, graph_version=graph_version,
    )
    guarded = OwnershipFencedChannelAdapter(
        database_url=database_url, downstream=provider,
        policy=policy, delivery_ledger=ledger,
    )
    return NotificationDeliveryWorker(
        store=store, adapters={"whatsapp":guarded},
        retry_policy=RetryPolicy(max_attempts=max_attempts),
        lease_seconds=60,
    )
