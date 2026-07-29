"""Contract used by workflows to execute agents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from rkjo_kernel.workflow.execution_result import ExecutionResult
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


class AgentExecutionAdapter(ABC):
    """Abstract an agent execution mechanism from the workflow engine.

    Concrete implementations may execute agents:

    - directly in the current process;
    - through the AgentOrchestrator;
    - through RabbitMQ;
    - through a remote execution service.
    """

    @abstractmethod
    def execute(
        self,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
    ) -> ExecutionResult:
        """Execute the agent associated with a workflow step.

        Implementations must return an ExecutionResult instead of
        modifying the workflow step lifecycle directly.
        """
        raise NotImplementedError
