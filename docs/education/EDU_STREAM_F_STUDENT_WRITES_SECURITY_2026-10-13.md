# Stream F — Student-owned writes (13 October 2026)

## Delivered on isolated Education branch
- Individual Bearer identity required for POST /education/attempts, POST /education/attempts/{id}/submit, GET/POST /education/proof-challenges/{id}(/submit).
- Tenant and learner identity are extracted from already validated middleware state. The request learner_id must match the Bearer subject UUID.
- The assessment lookup runs before grading; a cross-learner attempt returns 404.
- A cross-learner proof returns 404 before revealing its verification prompt or accepting a response.
- RBAC now allows VIEWER for these specific POST routes, but they independently reject operator keys or missing individual Bearer identities.
- AssessmentService.get_attempt() exposes tenant-scoped retrieval without reaching into private repository internals.
- Security tests added under tests/education/test_student_identity_guard.py, test_student_ownership_guards.py, test_student_submit_ownership.py and test_student_write_rbac.py.

## Migration / caveats
This is intentionally **breaking** for the legacy Next.js /api/education/attempts and /proof-challenges proxies, which currently pass an operator API key. Do not turn on student pilot use until these are migrated to individual sessions, backed by an authoritative UUID account-to-learner mapping. No default student account, query-string identity or operator-key bypass is permitted. These tests simulate already-validated JWT middleware and are not a replacement for actual JWT end-to-end and PostgreSQL integration tests.

## Mac validation
```bash
cd /Users/rkjo/Projects/rkjo-ai-platform-education-health
git pull --ff-only
PYTHONPATH=domains/education:platform/kernel:platform/api \
/Users/rkjo/Projects/rkjo-ai-platform/.venv/bin/python -m pytest -q \
  tests/education/test_student_identity_guard.py \
  tests/education/test_student_ownership_guards.py \
  tests/education/test_student_submit_ownership.py \
  tests/education/test_student_write_rbac.py \
  tests/education/test_assessment_next_action_api.py
npm --prefix apps/web run lint
npm --prefix apps/web run build
```
If any existing API or UI test fails due to a prior operator-key student workflow, treat it as a migration regression to fix without removing the ownership controls.
