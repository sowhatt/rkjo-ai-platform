from unittest.mock import Mock, patch

from rkjo_kernel.workflow.schema_bootstrap import (
    bootstrap_workflow_schema,
)


def test_bootstrap_uses_injected_database_url_and_initializes_schema():
    uow = Mock()

    with patch(
        "rkjo_kernel.workflow.schema_bootstrap.PostgreSQLWorkflowUnitOfWork",
        return_value=uow,
    ) as uow_class:
        bootstrap_workflow_schema(
            database_url="postgresql://rkjo:test@db:5432/rkjo",
        )

    uow_class.assert_called_once_with(
        "postgresql://rkjo:test@db:5432/rkjo"
    )
    uow.initialize_schema.assert_called_once_with()


def test_bootstrap_defaults_to_kernel_database_url():
    uow = Mock()

    with patch(
        "rkjo_kernel.workflow.schema_bootstrap.settings.database_url",
        "postgresql://rkjo:default@db:5432/rkjo",
    ), patch(
        "rkjo_kernel.workflow.schema_bootstrap.PostgreSQLWorkflowUnitOfWork",
        return_value=uow,
    ) as uow_class:
        bootstrap_workflow_schema()

    uow_class.assert_called_once_with(
        "postgresql://rkjo:default@db:5432/rkjo"
    )
    uow.initialize_schema.assert_called_once_with()
