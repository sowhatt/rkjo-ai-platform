"""Authenticated tenant-bound Omnichannel operational cockpit API.

GET: current queue health/alerts and latest incident states.
POST: operator incident acknowledgement; does not modify deliveries.
Schema bootstrap and alert synchronization run in separate controlled jobs.
"""
from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from rkjo_api.identity import get_authenticated_identity
from rkjo_kernel.omnichannel.incidents import PostgreSQLOmnichannelIncidents
from rkjo_kernel.omnichannel.monitoring import PostgreSQLOmnichannelMonitor
from rkjo_kernel.omnichannel.operations import PostgreSQLOmnichannelOperations


router = APIRouter(prefix="/omnichannel", tags=["omnichannel"])


def _identity(request: Request) -> tuple[str, str]:
    identity = get_authenticated_identity(request)
    if not identity.tenant_id or not identity.tenant_id.strip():
        # Never allow a privileged unbound API key to see cross-tenant telemetry.
        raise HTTPException(status_code=403, detail="Tenant-bound identity required.")
    return identity.tenant_id, identity.subject or "api-operator"


def _database_url() -> str:
    url = os.environ.get("RKJO_DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="Operational database unavailable.")
    return url


@router.get("/dashboard")
def dashboard(request: Request):
    tenant_id, _ = _identity(request)
    url = _database_url()
    now = datetime.now(timezone.utc)
    try:
        snapshot = PostgreSQLOmnichannelOperations(url).snapshot(
            tenant_id=tenant_id, now=now,
        )
        monitoring = PostgreSQLOmnichannelMonitor(
            operations=PostgreSQLOmnichannelOperations(url),
        ).check(tenant_id=tenant_id, now=now)
        incidents = PostgreSQLOmnichannelIncidents(url).list(
            tenant_id=tenant_id, limit=50,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Omnichannel dashboard unavailable.") from exc
    return {
        "tenant_id": tenant_id,
        "evaluated_at": now.isoformat(),
        "queues": {
            "inbound": asdict(snapshot.inbound),
            "routes": asdict(snapshot.routes),
            "outbound": asdict(snapshot.outbound),
        },
        "delivery": {
            "uncertain_outbound": snapshot.uncertain_outbound,
            "provider_confirmed_uncommitted": snapshot.provider_confirmed_uncommitted,
            "sent_without_binding": snapshot.sent_without_binding,
            "delivery_receipts": snapshot.delivery_receipts,
        },
        "healthy": monitoring.healthy,
        "alerts": [
            {"code": a.code, "severity": a.severity.value, "count": a.count}
            for a in monitoring.alerts
        ],
        "incidents": [
            {"code": i.code, "severity": i.severity, "status": i.status,
             "count": i.count, "last_seen_at": i.last_seen_at.isoformat(),
             "acknowledged_at": i.acknowledged_at.isoformat() if i.acknowledged_at else None}
            for i in incidents
        ],
    }


@router.post("/incidents/{code}/acknowledge")
def acknowledge_incident(code: str, request: Request):
    tenant_id, operator_id = _identity(request)
    if not code or len(code) > 128:
        raise HTTPException(status_code=422, detail="Invalid incident code.")
    try:
        incident = PostgreSQLOmnichannelIncidents(_database_url()).acknowledge(
            tenant_id=tenant_id, code=code, operator_id=operator_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Open incident not found.") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Incident store unavailable.") from exc
    return {"tenant_id": tenant_id, "code": incident.code,
            "status": incident.status, "acknowledged_by": incident.acknowledged_by}
