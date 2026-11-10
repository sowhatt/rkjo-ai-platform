from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rkjo_kernel.tools.binding import ToolBinding
from rkjo_kernel.tools.descriptor import ToolDescriptor


ToolHandler = Callable[
    [dict[str, Any], Any],
    Any,
]


@dataclass
class RegisteredTool:
    descriptor: ToolDescriptor
    handler: ToolHandler | None = None


class ToolRegistry:
    """In-memory registry of executable RKJO tools."""

    def __init__(self) -> None:
        self._tools: dict[
            str,
            RegisteredTool,
        ] = {}

        self._bindings: set[
            tuple[str, str]
        ] = set()

    def register(
        self,
        descriptor: ToolDescriptor,
        handler: ToolHandler | None = None,
    ) -> None:
        self._tools[
            descriptor.name
        ] = RegisteredTool(
            descriptor=descriptor,
            handler=handler,
        )

    def unregister(
        self,
        tool_name: str,
    ) -> None:
        normalized_name = (
            tool_name.strip().lower()
        )

        if normalized_name not in self._tools:
            raise KeyError(
                f"Tool '{normalized_name}' "
                "is not registered."
            )

        del self._tools[normalized_name]

        self._bindings = {
            binding
            for binding in self._bindings
            if binding[1] != normalized_name
        }

    def find_by_name(
        self,
        tool_name: str,
    ) -> ToolDescriptor | None:
        registered_tool = (
            self.get_registered_tool(
                tool_name
            )
        )

        if registered_tool is None:
            return None

        return registered_tool.descriptor

    def get_registered_tool(
        self,
        tool_name: str,
    ) -> RegisteredTool | None:
        normalized_name = (
            tool_name.strip().lower()
        )

        return self._tools.get(
            normalized_name
        )

    def list_tools(
        self,
    ) -> list[ToolDescriptor]:
        return [
            registered_tool.descriptor
            for registered_tool
            in self._tools.values()
        ]

    def bind(
        self,
        binding: ToolBinding,
    ) -> None:
        if (
            binding.tool_name
            not in self._tools
        ):
            raise KeyError(
                f"Tool '{binding.tool_name}' "
                "is not registered."
            )

        self._bindings.add(
            (
                binding.capability_name,
                binding.tool_name,
            )
        )

    def find_by_capability(
        self,
        capability_name: str,
    ) -> list[ToolDescriptor]:
        normalized_capability = (
            capability_name.strip().lower()
        )

        tool_names = [
            tool_name
            for bound_capability, tool_name
            in self._bindings
            if (
                bound_capability
                == normalized_capability
            )
        ]

        return [
            self._tools[
                tool_name
            ].descriptor
            for tool_name in tool_names
        ]

    def count(self) -> int:
        return len(self._tools)

    def count_bindings(self) -> int:
        return len(self._bindings)
