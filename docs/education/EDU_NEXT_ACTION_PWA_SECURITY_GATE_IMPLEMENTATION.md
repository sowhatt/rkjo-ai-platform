# RKJO Education — PWA NBA identity gate (13 October 2026)

## Delivered
- Added Next.js route `GET /api/education/attempts/[attemptId]/questions/[questionId]/next-action`.
- The current Education shared pilot session cannot impersonate an individual learner.
- Without pilot session: HTTP 401. With shared pilot session: HTTP 403. Both no-store.
- No operator API key, caller supplied learnerId, fake mastery, or backend forwarding.
- `tests/education/test_next_action_identity_gate.py` checks a static fail-closed contract (not a substitute for execution/browser tests).
- No changes to `main` or to the existing older operator-key routes.

## Blocking requirement for true integration
Design and test a genuine user authentication session with a tenant-scoped, server-verified mapping from account subject to learner UUID. Ensure FastAPI Bearer JWT tenant and subject UUID match authoritative learner storage; then replace the 403 with a server-generated short-lived Bearer forwarded only to the configured backend. Do not derive credentials from arbitrary query parameters. Protect the older attempt/proof proxy routes and FastAPI write routes with same ownership contract before enabling a full PWA learning path.

## Mac checks
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q \
tests/education/test_next_action_identity_gate.py \
tests/education/test_assessment_next_action_api.py
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
Expected: new route appears as a dynamic Next.js API endpoint. These checks have not yet been run on the Mac. Verify 401/403 at runtime in the local development pilot; never use production student data.
