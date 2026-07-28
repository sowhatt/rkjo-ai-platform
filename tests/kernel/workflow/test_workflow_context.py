from rkjo_kernel.workflow import WorkflowContext


def test_context_reads_variables_before_input_data():
    context = WorkflowContext(
        input_data={"customer_id": "input-value"},
        variables={"customer_id": "variable-value"},
    )

    assert context.get("customer_id") == "variable-value"


def test_context_reads_input_data_when_variable_is_missing():
    context = WorkflowContext(
        input_data={"customer_id": "C-001"}
    )

    assert context.get("customer_id") == "C-001"


def test_context_stores_variables_and_outputs():
    context = WorkflowContext()

    context.set_variable("validated", True)
    context.set_output("validation", {"status": "ok"})

    assert context.variables["validated"] is True
    assert context.outputs["validation"] == {"status": "ok"}


def test_context_snapshot_is_isolated():
    context = WorkflowContext(
        variables={"items": ["A"]}
    )

    snapshot = context.snapshot()
    snapshot["variables"]["items"].append("B")

    assert context.variables["items"] == ["A"]
