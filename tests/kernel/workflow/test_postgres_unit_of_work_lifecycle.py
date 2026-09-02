from unittest.mock import MagicMock

import pytest

from rkjo_kernel.workflow import postgres_unit_of_work
from rkjo_kernel.workflow.postgres_unit_of_work import (
    PostgreSQLWorkflowUnitOfWork,
)


DATABASE_URL = "postgresql://rkjo:test@localhost:5432/rkjo"


def _mock_connection(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr(
        postgres_unit_of_work.psycopg,
        "connect",
        MagicMock(return_value=connection),
    )
    return connection


def test_exit_rolls_back_uncommitted_work_and_releases_resources(
    monkeypatch,
):
    connection = _mock_connection(monkeypatch)
    uow = PostgreSQLWorkflowUnitOfWork(DATABASE_URL)

    with uow:
        assert uow._connection is connection
        assert uow.workflows is not None
        assert uow.inbox is not None
        assert uow.outbox is not None

    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()
    assert uow._connection is None
    assert uow.workflows is None
    assert uow.inbox is None
    assert uow.outbox is None


def test_exit_rolls_back_and_releases_resources_on_exception(
    monkeypatch,
):
    connection = _mock_connection(monkeypatch)
    uow = PostgreSQLWorkflowUnitOfWork(DATABASE_URL)

    with pytest.raises(RuntimeError, match="boom"):
        with uow:
            raise RuntimeError("boom")

    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()
    assert uow._connection is None
    assert uow.workflows is None
    assert uow.inbox is None
    assert uow.outbox is None


def test_explicit_commit_is_preserved_before_context_cleanup(
    monkeypatch,
):
    connection = _mock_connection(monkeypatch)
    uow = PostgreSQLWorkflowUnitOfWork(DATABASE_URL)

    with uow:
        uow.commit()

    connection.commit.assert_called_once_with()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()
