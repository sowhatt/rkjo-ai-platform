# OMNI-016.4.3.2 — RabbitMQ infrastructure monitoring (phase 1)

## Security boundary

`GET /internal/omnichannel/rabbitmq` is a **global infrastructure** view,
reserved for authenticated RKJO ADMIN users. It must never be exposed through
`GET /omnichannel/dashboard` or reused by tenant-bound Next.js proxy routes.
Shared RabbitMQ queues can carry events for multiple tenants.

The Management API user should have **read-only monitoring rights** with the
minimum permitted vhost scope. Never reuse the RabbitMQ publishing user's
credentials if they grant write permissions. Restrict network access to
internal services; never expose the Management API publicly.

## Environment (names only, no real secrets)

- `RKJO_OMNI_RABBITMQ_MANAGEMENT_URL` — e.g. `http://127.0.0.1:15672`;
  configure HTTPS for remote services.
- `RKJO_OMNI_RABBITMQ_MONITOR_USER` — monitoring principal.
- `RKJO_OMNI_RABBITMQ_MONITOR_PASSWORD` — secret injected at runtime.
- `RKJO_OMNI_RABBITMQ_VHOST` — vhost, defaults to `/`.
- `RKJO_OMNI_RABBITMQ_MONITORED_QUEUES` — comma-separated allowlist,
  e.g. `rkjo.omnichannel.agent,rkjo.omnichannel.agent.dlq`.

This does not discover queues or access message bodies. Nonexistent queues,
broker outages, unexpected responses and bad counter types produce HTTP 503,
without leaking secrets or broker response details.

## Metrics

For each configured queue: `messages_ready`, `messages_unacknowledged`,
`consumers`, `messages` and the `.dlq` suffix classification.
The summary gives the summed ready/unacked messages and sum of configured DLQs.
These metrics are broker snapshots, **not** durable tenant counters.
They are not end-to-end latency metrics.

## Local verification

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-omnichannel
source /Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/activate
git pull --ff-only origin feat/v2-omnichannel-runtime-v1
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
python3 -m pytest tests/api/test_omnichannel_rabbitmq_metrics.py -v
python3 -m pytest tests/api/test_omnichannel_cockpit_http.py -v
python3 -m pytest tests/kernel/omnichannel -q
cd apps/web && npm ci && npm exec -- tsc --noEmit && npm run build
```

## Remaining

- Actual staging RabbitMQ Management API smoke test using a read-only account.
- Infrastructure-only administration dashboard UI and alert thresholds.
- Tenant-isolated worker claim enforcement and true delivery latency probes.
- Regression testing of broker shutdown, reconnect, DLQ recovery and permissions.

No broker credentials should be committed, printed or attached to test logs.
