# OMNI-016.3 — Omnichannel operational monitoring

## Purpose

Evaluate tenant-scoped operational counters without reading message bodies
or sending data to Meta. This is a **pull-based diagnostic command**, not yet a
running alert dispatch integration. A scheduler/monitoring system can invoke
it periodically and act on the exit code.

The source of truth is `PostgreSQLOmnichannelOperations.snapshot` built in
OMNI-015.4. Only dedicated authorized operators should run the probe.
Its output contains tenant IDs and aggregate counters (no bearer tokens,
recipient references, webhook payloads, phone numbers, or DB credentials).

## Run

```bash
# RKJO_DATABASE_URL is injected by the deployment secret manager.
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD"
python3 -m rkjo_worker.omnichannel_monitor --tenant-id tenant-a
```

Optional limits:

```bash
python3 -m rkjo_worker.omnichannel_monitor \
  --tenant-id tenant-a \
  --inbound-backlog 100 \
  --route-backlog 100 \
  --outbound-backlog 50
```

Return codes: `0` no alert, `2` alert present, `3` infrastructure/configuration
failure. Do not treat a failed probe as a healthy system.

- **Warning** on configured inbound/outbox/outbound backlog thresholds.
- **Critical** whenever failed work or expired leases are detected.
- **Critical** whenever provider acceptance is uncertain, an accepted send
  is not finalized in the notification store, or a sent notification lacks
  a delivery-ledger binding.
- Alert dedup identity: `omnichannel:{tenant_id}:{code}`.

`delivery_receipts` is an overall counter, not a per-message SLA or proof
that *all* messages were delivered. A missing-receipt-age SLA needs a
separate time-bounded query and is not claimed here.

## Recommended operational deployment

Invoke every 1–5 minutes from an internal scheduler, with scoped read-only
database access where supported. Record counter trends in your metrics stack,
and page on critical alerts. A periodic check is not created automatically
by this code. Configure notification rate limiting and deduplication
externally to avoid alert flooding. Segregate tenant operations access.

Provider acceptance ambiguity requires human reconciliation, never a blind
resend. This probe performs no reconciliation and makes no mutations.

## Validation

```bash
python3 -m pytest tests/kernel/omnichannel/test_monitoring.py -v
python3 -m pytest tests/worker/test_omnichannel_monitor.py -v
python3 -m pytest tests/kernel/omnichannel -q
python3 -m pytest tests/kernel/multimodal -q
```

Next: run the probe with an actual isolated PostgreSQL test schema and
verify expected failure counters, then integrate with an authenticated
operational dashboard and an internal alert notification channel.
