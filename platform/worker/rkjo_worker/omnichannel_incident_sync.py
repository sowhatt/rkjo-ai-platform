"""OMNI-016.4 — explicit, tenant-scoped alert-to-incident sync.

Run from an internal scheduler with scoped DB credentials. This command
does not dispatch notifications, send WhatsApp messages, or mutate deliveries.
"""
from __future__ import annotations

import argparse
import json
import os

from rkjo_kernel.omnichannel.incidents import PostgreSQLOmnichannelIncidents
from rkjo_kernel.omnichannel.monitoring import PostgreSQLOmnichannelMonitor
from rkjo_kernel.omnichannel.operations import PostgreSQLOmnichannelOperations


def sync_tenant(*, tenant_id: str, database_url: str) -> dict:
    report = PostgreSQLOmnichannelMonitor(
        operations=PostgreSQLOmnichannelOperations(database_url),
    ).check(tenant_id=tenant_id)
    store = PostgreSQLOmnichannelIncidents(database_url)
    count = store.sync(report)
    return {
        "tenant_id": tenant_id,
        "active_alerts": count,
        "critical": report.has_critical,
        "healthy": report.healthy,
    }


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Synchronize RKJO Omnichannel incidents")
    parser.add_argument("--tenant-id",required=True)
    args=parser.parse_args(argv)
    try:
        if not args.tenant_id.strip():
            raise ValueError("Tenant required.")
        result=sync_tenant(
            tenant_id=args.tenant_id,
            database_url=os.environ["RKJO_DATABASE_URL"],
        )
    except Exception:
        print(json.dumps({"error":"OmnichannelIncidentSyncUnavailable"}))
        return 3
    print(json.dumps(result,sort_keys=True))
    return 2 if result["active_alerts"] else 0


if __name__=="__main__":
    raise SystemExit(main())
