"""Explicitly tenant-bound worker heartbeat publisher (no shared/global fallback)."""
from __future__ import annotations

from datetime import datetime, timezone
import os

from rkjo_kernel.omnichannel.worker_heartbeats import PostgreSQLOmnichannelWorkerHeartbeats


class TenantHeartbeatPublisher:
    def __init__(self, *, database_url: str, tenant_id: str,
                 worker_name: str):
        if not tenant_id or not tenant_id.strip():
            raise ValueError("Explicit tenant ID required.")
        self.tenant_id = tenant_id
        self.worker_name = worker_name
        self.store = PostgreSQLOmnichannelWorkerHeartbeats(database_url)

    def record(self, status: str, *, now: datetime | None = None) -> None:
        self.store.beat(
            tenant_id=self.tenant_id,
            worker_name=self.worker_name,
            status=status,
            at=now or datetime.now(timezone.utc),
        )


def configured_publisher(*, database_url: str, worker_name: str,
                         environ=None) -> TenantHeartbeatPublisher | None:
    env = os.environ if environ is None else environ
    tenant_id = env.get("RKJO_OMNI_WORKER_TENANT_ID")
    # An unbound, potentially cross-tenant worker must never be advertised
    # as dedicated to any one tenant.
    if not tenant_id:
        return None
    return TenantHeartbeatPublisher(
        database_url=database_url,
        tenant_id=tenant_id,
        worker_name=worker_name,
    )
