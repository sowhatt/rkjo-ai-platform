import os

from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.repository.postgres import (
    PostgreSQLWorkflowRepository,
)


def get_database_url() -> str:
    return os.getenv(
        "RKJO_DATABASE_URL",
        "postgresql://rkjo:rkjo_password@localhost:5432/rkjo",
    )


def get_workflow_repository() -> PostgreSQLWorkflowRepository:
    repository = PostgreSQLWorkflowRepository(
        get_database_url()
    )
    repository.initialize_schema()
    return repository


def get_workflow_engine() -> WorkflowEngine:
    return WorkflowEngine(
        repository=get_workflow_repository()
    )
