"""Bind HTTP workflow ownership to authenticated identity, never request data."""
from uuid import uuid4
from dataclasses import replace
import hashlib
from fastapi import Depends, HTTPException, Request
from rkjo_api.identity import AuthenticatedIdentity, get_authenticated_identity
from rkjo_kernel.workflow.models.workflow_execution import WorkflowExecution


def require_workflow_identity(request: Request, identity: AuthenticatedIdentity = Depends(get_authenticated_identity)) -> AuthenticatedIdentity:
    if not identity.tenant_id or not identity.tenant_id.strip():
        raise HTTPException(status_code=403, detail="Tenant-bound identity required for workflows.")
    if identity.subject is None:
        credential = request.headers.get("X-API-Key", "")
        if not credential:
            raise HTTPException(status_code=403, detail="Workflow principal required.")
        identity = replace(identity, subject="api-key:" + hashlib.sha256(credential.encode()).hexdigest()[:24])
    return identity


# Authority fields are never copied from request metadata. A matching tenant is
# accepted for compatibility; all other reserved fields must be server-created.
RESERVED = {"user_id", "subject", "role", "api_role", "policy_context", "permissions",
            "scopes", "mission_id", "trace_id", "request_id", "parent_span_id",
            "workflow_execution_id", "workflow_step_id", "agent_id", "capability_name",
            "reply_queue", "attempt", "retry_of_message_id", "result_signature"}


def bind_workflow_metadata(identity: AuthenticatedIdentity, metadata: dict) -> dict:
    if RESERVED.intersection(metadata) or any(k.startswith("retry_") for k in metadata):
        raise HTTPException(status_code=403, detail="Workflow authority is server-managed.")
    if "tenant_id" in metadata and metadata["tenant_id"] != identity.tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant workflow access is not permitted.")
    return {**metadata, "tenant_id": identity.tenant_id,
            "user_id": identity.subject,
            "policy_context": {"api_role": identity.role.value},
            "mission_id": str(uuid4()), "trace_id": str(uuid4()), "request_id": str(uuid4())}


def authorize_workflow(identity: AuthenticatedIdentity, execution: WorkflowExecution) -> None:
    # Both copies must agree. Legacy unbound executions require explicit migration.
    if (execution.metadata.get("tenant_id") != identity.tenant_id
            or execution.context.metadata.get("tenant_id") != identity.tenant_id):
        raise HTTPException(status_code=404, detail="Workflow execution not found.")


def authorize_workflow_start(identity: AuthenticatedIdentity, execution: WorkflowExecution) -> None:
    authorize_workflow(identity, execution)
    meta = execution.metadata
    if (meta != execution.context.metadata
            or any(not isinstance(meta.get(k), str) or not meta[k].strip()
                   for k in ("user_id", "mission_id", "trace_id", "request_id"))
            or meta.get("policy_context", {}).get("api_role") not in {"operator", "admin"}):
        raise HTTPException(status_code=404, detail="Workflow execution not found.")
