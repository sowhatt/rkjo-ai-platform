# OMNI-016.4 — operational cockpit (backend phase 1)

## Delivered

- `omni_operational_incidents` PostgreSQL incident current-state ledger. Its key is `(tenant_id, code)`; the latest occurrence and lifecycle state are retained. **This is not yet a full append-only event history.**
- `PostgreSQLOmnichannelIncidents.sync()`: explicit transaction-scoped reconciliation of monitored alerts, including auto-resolution after a healthy evaluation and re-opening after recurrence.
- `PostgreSQLOmnichannelIncidents.acknowledge()`: requires a supplied operator identity, and only transitions `open -> acknowledged`. Repeated acknowledgement returns not found/conflict at the service boundary.
- Protected REST endpoints: `GET /omnichannel/dashboard` (VIEWER), `POST /omnichannel/incidents/{code}/acknowledge` (OPERATOR). Authenticated identities **must** be tenant-bound even if they are admin.
- `rkjo_worker.omnichannel_incident_sync`: explicit, internal scheduler CLI. Zero external provider calls.

## Bootstrap

Initialize schema in a controlled migration/bootstrap phase:

```python
from rkjo_kernel.omnichannel.incidents import PostgreSQLOmnichannelIncidents
PostgreSQLOmnichannelIncidents(database_url).initialize_schema()
```

This assumes OMNI-015/016 tables have already been initialized.

## Scheduled sync (configure in your own scheduler)

```bash
# RKJO_DATABASE_URL is injected securely by deployment orchestration.
python3 -m rkjo_worker.omnichannel_incident_sync --tenant-id tenant-a
```

Exit codes: 0 clear, 2 one or more alerts, 3 infrastructure failure.
A scheduler should trigger this at a controlled interval, e.g. every 1–5 min,
**per authorized tenant**. There is no scheduler deployed by this commit.

## API security

The API's existing middleware now protects `/omnichannel`.
`GET /omnichannel/dashboard` requires VIEWER or above.
`POST /omnichannel/incidents/{code}/acknowledge` requires OPERATOR or above.

Identity tenant binding is required via JWT or configured role key mapping;
tenant is never taken from a client query parameter. An unbound legacy admin
API key cannot access these endpoints. Do not put provider tokens in responses.
Only expose the API through HTTPS.

The acknowledgement endpoint records `identity.subject` when available,
or `api-operator` for tenant-bound key authentication. For formal audit,
require individual operator identities instead of shared keys.

## Not yet delivered

- Browser dashboard/PWA layout and charts.
- Immutable append-only incident change history.
- External alert dispatch (email, Slack, etc.) and rate-limited delivery.
- Real-time transport (SSE/WebSocket), alert SLA, role-scoped per-account visibility.
- Full API integration tests with PostgreSQL and signed/tenant-bound HTTP credentials.
- Provider-live WhatsApp validation.

The new API is deliberately read-only for message flow; acknowledgement changes
incident workflow state only, never queue or provider state.

## Validation

```bash
python3 -m pytest tests/kernel/omnichannel/test_incidents.py -v
python3 -m pytest tests/api/test_omnichannel_cockpit.py -v
python3 -m pytest tests/worker/test_omnichannel_incident_sync.py -v
python3 -m pytest tests/kernel/omnichannel -q
python3 -m pytest tests/kernel/multimodal -q
```
