import pytest

from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.registry import ToolRegistry


def test_invoker_executes_registered_tool():
    registry = ToolRegistry()

    descriptor = ToolDescriptor(
        name="math.add",
        display_name="Add",
        description="Add two numbers.",
    )

    registry.register(
        descriptor,
        handler=lambda payload, context: (
            payload["left"] + payload["right"]
        ),
    )

    invoker = ToolInvoker(registry)

    result = invoker.invoke(
        tool_name="math.add",
        payload={
            "left": 2,
            "right": 3,
        },
    )

    assert result.success is True
    assert result.output == 5
    assert result.error is None


def test_invoker_returns_failure_for_unknown_tool():
    invoker = ToolInvoker(ToolRegistry())

    result = invoker.invoke(
        tool_name="missing.tool",
        payload={},
    )

    assert result.success is False
    assert result.output is None
    assert "not registered" in result.error


def test_invoker_captures_handler_failure():
    registry = ToolRegistry()

    registry.register(
        ToolDescriptor(
            name="broken.tool",
            display_name="Broken",
            description="Always fails.",
        ),
        handler=lambda payload, context: (
            1 / 0
        ),
    )

    result = ToolInvoker(registry).invoke(
        tool_name="broken.tool",
        payload={},
    )

    assert result.success is False
    assert result.output is None
    assert "division by zero" in result.error
