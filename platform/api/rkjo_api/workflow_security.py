"""Bind HTTP workflow ownership to authenticated identity, never request data."""
from fastapi import Depends, HTTPException
from rkjo_api.identity import AuthenticatedIdentity, get_authenticated_identity
from rkjo_kernel.workflow.models.workflow_execution import WorkflowExecution


def require_workflow_identity(identity: AuthenticatedIdentity = Depends(get_authenticated_identity)) -> AuthenticatedIdentity:
    if not identity.tenant_id or not identity.tenant_id.strip():
        raise HTTPException(status_code=403, detail="Tenant-bound identity required for workflows.")
    return identity


def bind_workflow_metadata(identity: AuthenticatedIdentity, metadata: dict) -> dict:
    if "tenant_id" in metadata and metadata["tenant_id"] != identity.tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant workflow access is not permitted.")
    return {**metadata, "tenant_id": identity.tenant_id}


def authorize_workflow(identity: AuthenticatedIdentity, execution: WorkflowExecution) -> None:
    # Both copies must agree. Legacy unbound executions require explicit migration.
    if (execution.metadata.get("tenant_id") != identity.tenant_id
            or execution.context.metadata.get("tenant_id") != identity.tenant_id):
        raise HTTPException(status_code=404, detail="Workflow execution not found.")
