# RKJO Family — Sprint 0

## Goal

Establish RKJO Family as an autonomous domain on top of RKJO-AI Platform without duplicating platform orchestration, registry, workflow, runtime, knowledge, LLM or observability components.

## Scope

- Bootstrap `domains/family/rkjo_family`.
- Define the `Household` aggregate as the functional and security boundary.
- Define household roles: `parent_admin`, `parent`, `child`.
- Support member-level permission claims.
- Enforce `tenant_id` and `household_id` consistency.
- Add a tenant-safe repository contract and in-memory implementation.
- Add `HouseholdService` for create/get/list/add-member operations.
- Declare capability-first contracts for Family.
- Add unit tests for household isolation and capability stability.
- Include Family in the production Docker image and Python path.

## Out of scope

- PostgreSQL household persistence.
- API routes and authentication wiring.
- Calendar Agent.
- Reminder Agent.
- Document Agent.
- Education Agent integration.
- Family Advisor.
- PWA/WhatsApp/voice interfaces.

## Acceptance criteria

1. `rkjo_family` imports as a first-class domain package.
2. A household can be created with a parent administrator.
3. A non-empty household without a parent administrator is rejected.
4. A household lookup is scoped by `tenant_id`.
5. A member from another tenant cannot be attached to a household.
6. The Family capability catalog exposes:
   - `family.management`
   - `family.calendar`
   - `family.reminder`
   - `document.understanding`
   - `education.tutoring`
   - `family.advice`
7. The Docker runtime includes both Education and Family domains.

## Local validation

```bash
cd /Users/rkjo/Projects/rkjo-ai-platform

git fetch origin
git checkout feat/family-sprint-0
git pull origin feat/family-sprint-0

export PYTHONPATH="$PWD/platform/api:$PWD/platform/worker:$PWD/platform/kernel:$PWD/domains/education:$PWD/domains/family:$PWD"

python - <<'PY'
import rkjo_family
print("rkjo_family OK")
PY

pytest -q tests/family
pytest -q

docker compose config >/dev/null
```

## Next sprint

Sprint 1 should add PostgreSQL persistence, API/IAM integration, household onboarding and the first executable Family capability (`family.management`), then introduce Reminder as the first specialized agent workflow.
