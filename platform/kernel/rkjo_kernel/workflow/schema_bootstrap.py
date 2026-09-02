"""Explicit PostgreSQL bootstrap for durable workflow tables.

This module is intentionally separate from worker/API startup. Production
must run it as a deployment step before services that consume workflow state.
"""

from __future__ import annotations

from rkjo_kernel.config.settings import settings
from rkjo_kernel.workflow.postgres_unit_of_work import (
    PostgreSQLWorkflowUnitOfWork,
)


def bootstrap_workflow_schema(
    *,
    database_url: str | None = None,
) -> None:
    """Create the durable workflow schema idempotently.

    ``initialize_schema`` uses ``CREATE ... IF NOT EXISTS`` and is therefore
    safe to run repeatedly during deployments. The database URL can be
    injected by tests or defaults to the central kernel configuration.
    """
    resolved_database_url = database_url or settings.database_url

    PostgreSQLWorkflowUnitOfWork(
        resolved_database_url
    ).initialize_schema()


def main() -> None:
    """CLI entry point used by deployment/bootstrap jobs."""
    bootstrap_workflow_schema()


if __name__ == "__main__":
    main()
