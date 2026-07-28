"""Exceptions raised by the Workflow domain."""


class WorkflowDomainError(Exception):
    """Base exception for Workflow domain errors."""


class InvalidWorkflowDefinitionError(WorkflowDomainError):
    """Raised when a workflow definition is invalid."""


class InvalidWorkflowTransitionError(WorkflowDomainError):
    """Raised when a workflow status transition is invalid."""


class InvalidStepTransitionError(WorkflowDomainError):
    """Raised when a workflow step status transition is invalid."""
