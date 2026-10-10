"""OMNI-016.2.3 — supervised WhatsApp Cloud API delivery worker.

Deploy with RKJO_OMNI_WHATSAPP_ACCOUNTS_JSON containing account metadata
and TOKEN ENVIRONMENT VARIABLE NAMES, never the tokens themselves.
Secrets are injected by the platform's secret manager at runtime.
The worker polls PostgreSQL; webhook receipts use the existing inbound path.

Example metadata (NO credentials):
[
  {"tenant_id":"tenant-a","channel_account_id":"phone-a",
   "phone_number_id":"12345678901","token_env":"RKJO_META_TOKEN_TENANT_A",
   "approved_templates":[{"id":"welcome","name":"welcome_fr","language_code":"fr"}]}
]
"""
from __future__ import annotations

import json
import os
import signal
import time
from collections.abc import Mapping, Callable
from datetime import datetime, timezone
from typing import Any

from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.omnichannel.whatsapp_cloud import WhatsAppAccount, WhatsAppTemplate
from rkjo_kernel.omnichannel.whatsapp_runtime import (
    ConfiguredWhatsAppRegistry, build_whatsapp_delivery_worker,
)


logger = get_logger(__name__)


def _required_str(item: Mapping[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid WhatsApp configuration field: {field}.")
    return value.strip()


def load_whatsapp_registry(
    *, environ: Mapping[str, str] | None = None,
) -> ConfiguredWhatsAppRegistry:
    """Fail closed if metadata, secret references or tenant binding are invalid.

    Inline tokens are rejected to avoid accidental secret exposure through
    configuration files, diagnostic dumps and version control.
    """
    env = os.environ if environ is None else environ
    raw = env.get("RKJO_OMNI_WHATSAPP_ACCOUNTS_JSON")
    if not raw:
        raise ValueError("RKJO_OMNI_WHATSAPP_ACCOUNTS_JSON is required.")
    try:
        entries = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("WhatsApp account registry must be valid JSON.") from exc
    if not isinstance(entries, list) or not entries:
        raise ValueError("WhatsApp account registry must be a nonempty list.")
    accounts: dict[tuple[str, str], WhatsAppAccount] = {}
    approved: dict[tuple[str, str, str], WhatsAppTemplate] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("WhatsApp account entry must be an object.")
        permitted = {
            "tenant_id", "channel_account_id", "phone_number_id",
            "token_env", "approved_templates",
        }
        if set(entry) - permitted:
            raise ValueError("Unexpected WhatsApp account configuration fields.")
        tenant = _required_str(entry, "tenant_id")
        account = _required_str(entry, "channel_account_id")
        phone = _required_str(entry, "phone_number_id")
        token_env = _required_str(entry, "token_env")
        if not token_env.startswith("RKJO_META_TOKEN_") or not token_env.replace("_", "").isalnum():
            raise ValueError("WhatsApp secret reference must use RKJO_META_TOKEN_*.")
        token = env.get(token_env)
        if not token or not token.strip():
            raise ValueError("Referenced Meta access token is unavailable.")
        key = tenant, account
        if key in accounts:
            raise ValueError("Duplicate tenant/account WhatsApp binding.")
        accounts[key] = WhatsAppAccount(tenant, account, phone, token)
        templates = entry.get("approved_templates", [])
        if not isinstance(templates, list):
            raise ValueError("approved_templates must be an array.")
        for item in templates:
            if not isinstance(item, dict) or set(item) != {"id", "name", "language_code"}:
                raise ValueError("Invalid approved template metadata.")
            template_id = _required_str(item, "id")
            template_key = tenant, account, template_id
            if template_key in approved:
                raise ValueError("Duplicate approved template binding.")
            approved[template_key] = WhatsAppTemplate(
                name=_required_str(item, "name"),
                language_code=_required_str(item, "language_code"),
            )
    return ConfiguredWhatsAppRegistry(
        accounts=accounts, approved_templates=approved,
    )


class SupervisedWhatsAppDelivery:
    """One process, bounded polling and safe shutdown (no auto schema migration)."""

    def __init__(
        self, *, worker, poll_seconds: float = 1.0,
        batch_size: int = 50, sleep_fn: Callable[[float], None] = time.sleep,
        now_fn: Callable[[], datetime] | None = None,
    ):
        if not 0.1 <= poll_seconds <= 60 or not 1 <= batch_size <= 1000:
            raise ValueError("Invalid WhatsApp polling configuration.")
        self.worker = worker
        self.poll_seconds = poll_seconds
        self.batch_size = batch_size
        self.sleep_fn = sleep_fn
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.running = True

    def stop(self):
        self.running = False

    def run_cycle(self) -> int:
        processed = 0
        for _ in range(self.batch_size):
            if not self.running or not self.worker.run_once(now=self.now_fn()):
                break
            processed += 1
        return processed

    def run(self):
        while self.running:
            try:
                completed = self.run_cycle()
            except Exception:
                # Do not dump exception detail: credentials may be present in
                # lower-level transport errors or provider responses.
                logger.error("WhatsApp delivery worker cycle interrupted (details suppressed).")
                completed = 0
            if self.running and completed < self.batch_size:
                self.sleep_fn(self.poll_seconds)


def main() -> None:
    database_url = os.environ["RKJO_DATABASE_URL"]
    registry = load_whatsapp_registry()
    max_attempts = int(os.getenv("RKJO_OMNI_NOTIFICATION_MAX_ATTEMPTS", "4"))
    worker = build_whatsapp_delivery_worker(
        database_url=database_url, registry=registry,
        graph_version=os.getenv("RKJO_META_GRAPH_VERSION", "v23.0"),
        max_attempts=max_attempts,
    )
    supervisor = SupervisedWhatsAppDelivery(
        worker=worker,
        poll_seconds=float(os.getenv("RKJO_OMNI_DELIVERY_POLL_SECONDS", "1")),
        batch_size=int(os.getenv("RKJO_OMNI_DELIVERY_BATCH_SIZE", "50")),
    )

    def stop(_signum, _frame):
        supervisor.stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    supervisor.run()


if __name__ == "__main__":
    main()
