"""OMNI-016.3 — one-shot read-only operational probe.

Run from a controlled environment with database read permissions:
  python -m rkjo_worker.omnichannel_monitor --tenant-id TENANT

Exit codes: 0 healthy, 2 alert(s), 3 probe/config failure.
Do not include credentials, payloads or PII in stdout or stderr.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict

from rkjo_kernel.omnichannel.monitoring import (
    AlertThresholds, PostgreSQLOmnichannelMonitor,
)
from rkjo_kernel.omnichannel.operations import PostgreSQLOmnichannelOperations


def probe(*, tenant_id: str, database_url: str,
          thresholds: AlertThresholds | None = None) -> dict:
    monitor=PostgreSQLOmnichannelMonitor(
        operations=PostgreSQLOmnichannelOperations(database_url),
        thresholds=thresholds,
    )
    result=monitor.check(tenant_id=tenant_id)
    return {
        "tenant_id":result.tenant_id,
        "evaluated_at":result.evaluated_at.isoformat(),
        "healthy":result.healthy,
        "has_critical":result.has_critical,
        "alerts":[{
            "code":a.code, "severity":a.severity.value,
            "count":a.count, "dedup_key":a.dedup_key,
        } for a in result.alerts],
    }


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(
        description="RKJO Omnichannel tenant-scoped operational check"
    )
    parser.add_argument("--tenant-id",required=True)
    parser.add_argument("--inbound-backlog",type=int,default=100)
    parser.add_argument("--route-backlog",type=int,default=100)
    parser.add_argument("--outbound-backlog",type=int,default=50)
    args=parser.parse_args(argv)
    try:
        if not args.tenant_id.strip():
            raise ValueError("Tenant required.")
        result=probe(
            tenant_id=args.tenant_id,
            database_url=os.environ["RKJO_DATABASE_URL"],
            thresholds=AlertThresholds(
                inbound_backlog=args.inbound_backlog,
                route_backlog=args.route_backlog,
                outbound_backlog=args.outbound_backlog,
            ),
        )
    except Exception:
        # Database driver errors can contain DSNs. Do not expose details.
        print(json.dumps({"healthy":False,"error":"OmnichannelProbeUnavailable"}))
        return 3
    print(json.dumps(result,sort_keys=True))
    return 0 if result["healthy"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
