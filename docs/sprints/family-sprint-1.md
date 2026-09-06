# RKJO Family — Sprint 1

## Goal

Turn the Sprint 0 household domain into a usable, tenant-safe Family onboarding slice backed by PostgreSQL and exposed through the authenticated RKJO API.

## Scope

- PostgreSQL persistence for `Household` aggregates
- strict `(tenant_id, household_id)` isolation
- authenticated Family API under `/family`
- household creation with mandatory parent administrator
- household listing and lookup
- member onboarding
- automatic `family.management` permission for the initial parent administrator
- Family routes protected by the existing RKJO API RBAC middleware
- unit tests for onboarding, tenant isolation and RBAC

## API

- `POST /family/households`
- `GET /family/households`
- `GET /family/households/{household_id}`
- `POST /family/households/{household_id}/members`

The client never supplies `tenant_id`. It is taken only from the authenticated RKJO identity.

## Persistence

Table: `family_households`

Primary key:

- `tenant_id`
- `household_id`

The aggregate is stored with members in JSONB for the MVP onboarding slice. This keeps the domain aggregate atomic while leaving room for normalized projections later if required by query or analytics workloads.

## Security acceptance

1. `/family` is a protected API prefix.
2. Family reads require at least `viewer`.
3. Family writes require at least `operator`.
4. Household tenant comes from the authenticated identity.
5. Cross-tenant lookup cannot return another tenant's household.
6. Cross-tenant member attachment is rejected by the domain service.

## Validation

```bash
export PYTHONPATH="$PWD/platform/api:$PWD/platform/worker:$PWD/platform/kernel:$PWD/domains/education:$PWD/domains/family:$PWD"

pytest -q tests/family
pytest -q
docker compose config >/dev/null
```

## Exit criteria

Sprint 1 is complete when Family tests, the full suite and Docker Compose configuration are green on `feat/family-sprint-1`.

## Next sprint

Sprint 2 introduces the first time-based Family capability: reminder/calendar models and the first executable Family workflow through the RKJO capability/runtime layer.
