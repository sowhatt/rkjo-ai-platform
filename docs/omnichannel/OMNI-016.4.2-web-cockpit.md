# OMNI-016.4.2 — Web Cockpit, first usable UI

## Implemented

- `/omnichannel`: live tenant-scoped monitoring UI displaying queue states,
  active alerts, delivery discrepancies, and incident acknowledgement.
- `/dashboard`: entry link to Omnichannel.
- Next.js server routes `/api/omnichannel/dashboard` (GET) and
  `/api/omnichannel/incidents/[code]/acknowledge` (POST) proxy through
  `RKJO_API_URL` to FastAPI, **requiring a caller-provided Bearer token**.
- The token is kept only in transient React component state. There is no
  localStorage, cookie, query-string, or embedded shared server API key.
- FastAPI security middleware enforces VIEWER for dashboard, OPERATOR for
  acknowledgement, and requires a tenant-bound identity for both.
- Next proxies enforce no-cache responses, JSON content and timeouts. No
  cross-tenant filter from browser input is supported.
- No fake operational values or claims about RabbitMQ health are displayed.

## Local run

Start FastAPI with `RKJO_DATABASE_URL` pointing to an initialized development
database and a tenant-bound bearer/JWT authorization setup. Run Next.js:

```bash
cd apps/web
npm install
RKJO_API_URL=http://127.0.0.1:8000 npm run dev
```

Visit `http://localhost:3000/omnichannel`. Enter a **short-lived,
tenant-bound user JWT** obtained through your configured RKJO identity
provider. A viewer can inspect; an operator may acknowledge.

This UI deliberately does **not** accept or reuse server-side shared
`RKJO_VIEWER_API_KEY` as automatic user authorization. Production should
replace the manual token field with managed session-based authentication,
suitable XSS mitigation, and audited individual operator identity.

## Verification

```bash
export PYTHONPATH="$PWD/platform/kernel:$PWD/platform/api:$PWD/platform/worker:$PWD/domains/education:$PWD"
python3 -m pytest tests/api/test_omnichannel_cockpit_http.py -v
python3 -m pytest tests/api/test_omnichannel_cockpit.py -v
python3 -m pytest tests/kernel/omnichannel -q
cd apps/web
npx tsc --noEmit
npm run build
```

No browser automation, real JWT end-to-end deployment, RabbitMQ dashboard
metrics, SSE, durable immutable incident audit log, or visual acceptance
testing is claimed by this commit.
