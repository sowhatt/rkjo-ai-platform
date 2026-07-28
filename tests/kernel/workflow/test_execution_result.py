import pytest

from rkjo_kernel.workflow import ExecutionResult


def test_success_result_contains_output():
    result = ExecutionResult.succeeded(
        output={"customer_id": "C-001"},
        metadata={"agent": "validation_agent"},
        duration_ms=12.5,
    )

    assert result.success is True
    assert result.is_failure is False
    assert result.output == {"customer_id": "C-001"}
    assert result.error is None
    assert result.metadata == {
        "agent": "validation_agent"
    }
    assert result.duration_ms == 12.5


def test_failed_result_contains_error():
    result = ExecutionResult.failed(
        error="Agent unavailable",
        duration_ms=4.2,
    )

    assert result.success is False
    assert result.is_failure is True
    assert result.error == "Agent unavailable"
    assert result.duration_ms == 4.2


def test_success_result_rejects_error():
    with pytest.raises(
        ValueError,
        match="successful execution result",
    ):
        ExecutionResult(
            success=True,
            error="Unexpected error",
        )


def test_failed_result_requires_error():
    with pytest.raises(
        ValueError,
        match="requires an error message",
    ):
        ExecutionResult(
            success=False,
        )


def test_failed_result_rejects_blank_error():
    with pytest.raises(
        ValueError,
        match="requires an error message",
    ):
        ExecutionResult.failed(
            error="   ",
        )


def test_result_rejects_negative_duration():
    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        ExecutionResult.succeeded(
            duration_ms=-1,
        )


def test_factory_copies_metadata():
    metadata = {"attempt": 1}

    result = ExecutionResult.succeeded(
        metadata=metadata,
    )

    metadata["attempt"] = 2

    assert result.metadata["attempt"] == 1


def test_result_metadata_is_not_shared():
    first = ExecutionResult.succeeded()
    second = ExecutionResult.succeeded()

    first.metadata["request_id"] = "REQ-001"

    assert second.metadata == {}
