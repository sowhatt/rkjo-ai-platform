# OMNI-016.4.3 — tenant worker heartbeats and cockpit polling (phase 1)

## Delivered

- PostgreSQL table `omni_worker_heartbeats` with tenant and worker key,
  last observed status and UTC timestamp.
- Postgres upsert fencing prevents an older heartbeat overwriting a newer one.
- `GET /omnichannel/dashboard` includes `workers`, without raw
  exceptions, secrets, bearer tokens, RabbitMQ credentials or client data.
- A worker is marked `stale` after 90 seconds without an update.
- Next.js UI shows worker cards; opt-in auto-refresh every 30 seconds, only
  while the tab is visible and the user-provided bearer is present.
- Worker integration supports `ready` after successful processing cycles
  and `degraded` after errors.

## Critical deployment limitation

The current routing and WhatsApp worker loops are **not yet enforced as
tenant-specific by their DB claim queries**. Merely setting
`RKJO_OMNI_WORKER_TENANT_ID` does NOT restrict their work to that tenant.
Only configure this variable for a deployment whose isolation and worker
assignment are enforced externally; otherwise omit it. When omitted,
these loops do not publish a misleading tenant heartbeat. A later
sprint should enforce query-level tenant scope for dedicated workers
or adopt a separate operator-only deployment-wide health plane.

These are process-cycle heartbeats, **not direct RabbitMQ queue depth,
consumer count, DLQ status, or end-to-end message delivery proof**.
Do not interpret a green heartbeat as a healthy broker.

## Schema

Initialize via controlled bootstrap/migration, not on HTTP request:

```python
from rkjo_kernel.omnichannel.worker_heartbeats import PostgreSQLOmnichannelWorkerHeartbeats
PostgreSQLOmnichannelWorkerHeartbeats(database_url).initialize_schema()
```

Without initialization, the dashboard returns a 503 until the schema is
installed, as it should (fail closed). Do not expose raw DB errors.

## Tests

```bash
python3 -m pytest tests/kernel/omnichannel/test_worker_heartbeats.py -v
python3 -m pytest tests/worker/test_omnichannel_heartbeat.py -v
python3 -m pytest tests/api/test_omnichannel_cockpit_http.py -v
python3 -m pytest tests/kernel/omnichannel -q
python3 -m pytest tests/worker/test_omnichannel_whatsapp_delivery.py -q

cd apps/web
npm ci
npm exec -- tsc --noEmit
npm run build
```

## Not yet delivered

- Authenticated browser-session UX (user-provided short-lived Bearer remains).
- Validated tenant isolation at worker claim level.
- Actual RabbitMQ Management API metrics (queue, consumers, DLQ).
- Immutable incident audit, automated notifications and SSE.
- End-to-end deployment checks and failover tests.

Do not merge until Mac CI/test verification and operational tenant isolation
decision are complete.
