"""Administrator-only infrastructure RabbitMQ metrics. Not a tenant API."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from rkjo_api.identity import get_authenticated_identity
from rkjo_api.security import ApiRole
from rkjo_kernel.omnichannel.rabbitmq_alerts import (BrokerThresholds, evaluate_broker_alerts)
from rkjo_kernel.omnichannel.rabbitmq_telemetry import (
    RabbitMQQueueProbe, sanitized_snapshot,
)

router = APIRouter(prefix="/internal/omnichannel", tags=["omnichannel-internal"])


@router.get("/rabbitmq")
def rabbitmq_metrics(request: Request):
    identity = get_authenticated_identity(request)
    # Defense-in-depth, on top of authentication middleware.
    if identity.role != ApiRole.ADMIN or identity.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Administrator role required.")
    try:
        allowlist = [
            name.strip() for name in os.environ["RKJO_OMNI_RABBITMQ_MONITORED_QUEUES"].split(",")
        ]
        probe = RabbitMQQueueProbe(
            base_url=os.environ["RKJO_OMNI_RABBITMQ_MANAGEMENT_URL"],
            username=os.environ["RKJO_OMNI_RABBITMQ_MONITOR_USER"],
            password=os.environ["RKJO_OMNI_RABBITMQ_MONITOR_PASSWORD"],
            vhost=os.getenv("RKJO_OMNI_RABBITMQ_VHOST", "/"),
            queue_names=allowlist,
        )
        queues = probe.snapshot()
        thresholds = BrokerThresholds(
            ready_warning=int(os.getenv("RKJO_OMNI_RABBITMQ_READY_WARNING", "100")),
            ready_critical=int(os.getenv("RKJO_OMNI_RABBITMQ_READY_CRITICAL", "1000")),
            unacked_warning=int(os.getenv("RKJO_OMNI_RABBITMQ_UNACKED_WARNING", "100")),
            dlq_warning=int(os.getenv("RKJO_OMNI_RABBITMQ_DLQ_WARNING", "1")),
        )
        result = sanitized_snapshot(queues)
        result["alerts"] = evaluate_broker_alerts(queues, thresholds)
        result["healthy"] = not result["alerts"]
    except Exception:
        # Fail closed. Never leak management URLs, credentials or queue config.
        raise HTTPException(status_code=503, detail="Broker monitoring unavailable.") from None
    return {"evaluated_at": datetime.now(timezone.utc).isoformat(), **result}
