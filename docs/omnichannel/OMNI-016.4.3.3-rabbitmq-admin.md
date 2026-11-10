# OMNI-016.4.3.3 — Broker operations console and deterministic alerts

## Delivered

- Infrastructure-only page: `/admin/omnichannel/rabbitmq`.
- Server proxy: `/api/internal/omnichannel/rabbitmq`. Uses request Bearer only,
  never a shared server credential. No localStorage, no cookies or persisted JWT.
- Infrastructure-only FastAPI endpoint: `GET /internal/omnichannel/rabbitmq`.
- Defense-in-depth: requires ADMIN role and **no tenant binding**.
  Tenant-bound admins are denied (403), preventing leakage from shared queues.
- Five-minute absence, message age and message rates are NOT claimed as measured;
  available data are point-in-time ready, unacked, consumers and DLQ total.
- Optional 30-second UI refresh, visible browser tab only.
- Alert codes: DLQ_NONEMPTY (critical), QUEUE_NO_CONSUMER (critical),
  QUEUE_BACKLOG (warning), QUEUE_BACKLOG_CRITICAL (critical), QUEUE_UNACKED (warning).
  DLQs intentionally do not alert for zero consumers.

## Threshold settings (positive integer counts)

- `RKJO_OMNI_RABBITMQ_READY_WARNING` default 100.
- `RKJO_OMNI_RABBITMQ_READY_CRITICAL` default 1000 (> warning).
- `RKJO_OMNI_RABBITMQ_UNACKED_WARNING` default 100.
- `RKJO_OMNI_RABBITMQ_DLQ_WARNING` default 1.

Existing Management API settings from OMNI-016.4.3.2 still apply.
Only the configured queue allowlist is read. Disable public access to the
Management API; use read-only monitoring credentials in a private network.

Alerts are **current snapshots only**. No notification delivery, incident
persistence, history or automatic DLQ requeue is included. A 503 must be
treated as unavailable telemetry, not as healthy.

## Validation on Mac

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
python3 -m pytest tests/kernel/omnichannel/test_rabbitmq_alerts.py -v
python3 -m pytest tests/api/test_omnichannel_rabbitmq_admin.py -v
python3 -m pytest tests/api/test_omnichannel_rabbitmq_metrics.py -v
python3 -m pytest tests/kernel/omnichannel -q
cd apps/web
npm ci
npm exec -- tsc --noEmit
npm run build
```

## Before operational deployment

Verify an actual RabbitMQ Management API with least-privilege credentials,
real queue names/vhost and real DLQ. Conduct browser authorization tests
with admin, tenant-admin, viewer and expired JWT. Validate gateway controls,
CSRF/CSP, login/session integration and rate limiting. Never merge solely
because these unit tests pass.
