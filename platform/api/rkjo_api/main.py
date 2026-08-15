from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from rkjo_api.dependencies import (
    get_workflow_engine,
    get_workflow_repository,
)
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.repository.postgres import (
    PostgreSQLWorkflowRepository,
)


app = FastAPI(
    title="RKJO AI Platform API",
    version="0.1.0",
)


class HealthResponse(BaseModel):
    status: str


class WorkflowExecutionResponse(BaseModel):
    execution_id: str
    workflow_id: str
    status: str
    current_step_id: str | None
    error: str | None
    progress: float


@app.get(
    "/health",
    response_model=HealthResponse,
)
def health() -> HealthResponse:
    return HealthResponse(
        status="alive"
    )


@app.get(
    "/ready",
    response_model=HealthResponse,
)
def ready(
    repository: PostgreSQLWorkflowRepository = Depends(
        get_workflow_repository
    ),
) -> HealthResponse:
    try:
        repository.initialize_schema()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable.",
        ) from exc

    return HealthResponse(
        status="ready"
    )


@app.get(
    "/workflows/executions/{execution_id}",
    response_model=WorkflowExecutionResponse,
)
def get_execution(
    execution_id: str,
    engine: WorkflowEngine = Depends(
        get_workflow_engine
    ),
) -> WorkflowExecutionResponse:
    try:
        execution = engine.load_execution(
            execution_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Workflow execution not found.",
        ) from exc

    return WorkflowExecutionResponse(
        execution_id=execution.execution_id,
        workflow_id=execution.definition.workflow_id,
        status=execution.status.value,
        current_step_id=execution.current_step_id,
        error=execution.error,
        progress=execution.progress(),
    )
