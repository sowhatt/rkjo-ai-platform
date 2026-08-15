from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Any

from pydantic import BaseModel, Field

from rkjo_api.jwt_auth import (
    resolve_jwt_role,
)

from rkjo_api.security import (
    API_KEY_HEADER,
    is_protected_path,
    required_role_for_request,
    resolve_api_role,
    role_allows,
)

from rkjo_api.dependencies import (
    get_async_dispatcher,
    get_metrics_registry,
    get_workflow_agent_router,
    get_workflow_engine,
    get_workflow_repository,
)
from rkjo_kernel.monitoring.metrics import MetricsRegistry
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
from rkjo_kernel.workflow.exceptions import InvalidWorkflowTransitionError
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_step import (
    WorkflowStep,
)
from rkjo_kernel.workflow.repository.postgres import (
    PostgreSQLWorkflowRepository,
)


app = FastAPI(
    title="RKJO AI Platform API",
    version="0.1.0",
)




@app.middleware("http")
async def api_key_security(
    request: Request,
    call_next,
):
    """Protect operational and workflow API resources."""

    if not is_protected_path(
        request.url.path
    ):
        return await call_next(
            request
        )

    role = None
    subject = None

    authorization = request.headers.get(
        "Authorization"
    )

    if (
        authorization
        and authorization.startswith(
            "Bearer "
        )
    ):
        token = authorization[
            len("Bearer "):
        ].strip()

        try:
            subject, role = (
                resolve_jwt_role(
                    token
                )
            )

        except RuntimeError:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "JWT authentication "
                        "is not configured."
                    )
                },
            )

        except Exception:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": (
                        "Invalid or expired JWT."
                    )
                },
                headers={
                    "WWW-Authenticate": "Bearer"
                },
            )

    else:
        try:
            role = resolve_api_role(
                request.headers.get(
                    API_KEY_HEADER
                )
            )

        except RuntimeError:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "API authentication "
                        "is not configured."
                    )
                },
            )

        if role is None:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": (
                        "Invalid or missing credentials."
                    )
                },
            )

    required_role = (
        required_role_for_request(
            method=request.method,
            path=request.url.path,
        )
    )

    if not role_allows(
        actual_role=role,
        required_role=required_role,
    ):
        return JSONResponse(
            status_code=403,
            content={
                "detail": (
                    "Insufficient permissions."
                )
            },
        )

    request.state.api_role = role.value

    if subject is not None:
        request.state.api_subject = subject

    return await call_next(
        request
    )


class MetricsResponse(BaseModel):
    counters: dict[str, int]


class HealthResponse(BaseModel):
    status: str




class WorkflowStepRequest(BaseModel):
    step_id: str
    name: str
    agent_name: str | None = None
    capability_name: str | None = None
    description: str | None = None
    position: int = 0
    input_mapping: dict[str, Any] = Field(
        default_factory=dict
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class CreateWorkflowExecutionRequest(BaseModel):
    workflow_id: str
    name: str
    version: str = "1.0.0"
    description: str | None = None
    steps: list[WorkflowStepRequest]
    input_data: dict[str, Any] = Field(
        default_factory=dict
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )
    execution_id: str | None = None


class WorkflowDispatchResponse(BaseModel):
    execution_id: str
    workflow_id: str
    status: str
    step_id: str
    queue_name: str
    message_id: str
    correlation_id: str


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


@app.post(
    "/workflows/executions",
    response_model=WorkflowExecutionResponse,
    status_code=201,
)
def create_execution(
    request: CreateWorkflowExecutionRequest,
    engine: WorkflowEngine = Depends(
        get_workflow_engine
    ),
) -> WorkflowExecutionResponse:
    try:
        definition = WorkflowDefinition(
            workflow_id=request.workflow_id,
            name=request.name,
            version=request.version,
            description=request.description,
            steps=[
                WorkflowStep(
                    step_id=step.step_id,
                    name=step.name,
                    agent_name=step.agent_name,
                    capability_name=step.capability_name,
                    description=step.description,
                    position=step.position,
                    input_mapping=step.input_mapping,
                    metadata=step.metadata,
                )
                for step in request.steps
            ],
        )

        execution = engine.create_execution(
            definition,
            input_data=request.input_data,
            metadata=request.metadata,
            execution_id=request.execution_id,
        )

    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return WorkflowExecutionResponse(
        execution_id=execution.execution_id,
        workflow_id=execution.definition.workflow_id,
        status=execution.status.value,
        current_step_id=execution.current_step_id,
        error=execution.error,
        progress=execution.progress(),
    )


@app.post(
    "/workflows/executions/{execution_id}/start",
    response_model=WorkflowDispatchResponse,
    status_code=202,
)
def start_execution(
    execution_id: str,
    engine: WorkflowEngine = Depends(
        get_workflow_engine
    ),
    dispatcher: AsyncWorkflowDispatcher = Depends(
        get_async_dispatcher
    ),
    router: WorkflowAgentRouter = Depends(
        get_workflow_agent_router
    ),
) -> WorkflowDispatchResponse:
    try:
        execution = engine.load_execution(
            execution_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Workflow execution not found.",
        ) from exc

    try:
        engine.start(execution)

        step = engine.start_next_step(
            execution
        )

        if step is None:
            raise ValueError(
                "Workflow has no executable step."
            )

        route = router.resolve(
            step
        )

        result = dispatcher.dispatch(
            step=step,
            context=execution.context,
            queue_name=route.queue_name,
            execution_id=execution.execution_id,
            reply_queue="rkjo.workflow.results",
        )

    except (
        ValueError,
        InvalidWorkflowTransitionError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return WorkflowDispatchResponse(
        execution_id=execution.execution_id,
        workflow_id=execution.definition.workflow_id,
        status=execution.status.value,
        step_id=result.step_id,
        queue_name=result.queue_name,
        message_id=result.message_id,
        correlation_id=result.correlation_id,
    )


@app.get(
    "/metrics",
    response_model=MetricsResponse,
)
def metrics(
    registry: MetricsRegistry = Depends(
        get_metrics_registry
    ),
) -> MetricsResponse:
    return MetricsResponse(
        counters=registry.snapshot()
    )
