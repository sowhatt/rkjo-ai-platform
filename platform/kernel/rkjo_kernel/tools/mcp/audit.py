"""Audit records for MCP tool execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MCPExecutionAuditRecord:
    server_name: str
    remote_tool_name: str
    tenant_id: str
    agent_name: str
    capability_name: str
    workflow_execution_id: str | None
    workflow_step_id: str | None
    correlation_id: str | None
    duration_ms: int
    success: bool
    error_type: str | None = None
    metadata: dict[str, Any] | None = None


class MCPAuditSink(ABC):
    @abstractmethod
    def record(self, event: MCPExecutionAuditRecord) -> None:
        raise NotImplementedError


class NullMCPAuditSink(MCPAuditSink):
    def record(self, event: MCPExecutionAuditRecord) -> None:
        return None


class InMemoryMCPAuditSink(MCPAuditSink):
    def __init__(self) -> None:
        self.events: list[MCPExecutionAuditRecord] = []

    def record(self, event: MCPExecutionAuditRecord) -> None:
        self.events.append(event)
