"""Education supervision HTTP API."""

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import StreamingResponse

from rkjo_api.education import require_uuid_tenant
from rkjo_api.education_dependencies import get_education_event_publisher, get_education_proof_service
from rkjo_education.events import EducationEventPublisher, EducationEventType, EducationLearningEvent
from rkjo_education.intelligence.proof_application import ProofApplicationService, ProofQuestionNotFoundError
from rkjo_api.dependencies import get_database_url
from rkjo_education.supervision import (
    LearnerSupervisionProjection,
    LearnerSupervisionState,
)
from rkjo_education.supervision.alerts import SupervisionAlert, alerts_for_state
from rkjo_education.supervision.history import PostgresLearningEventHistory
from rkjo_education.supervision.interventions import (
    TeacherIntervention,
    PostgresTeacherInterventionStore,
    TeacherInterventionType,
)
from pydantic import BaseModel, Field

class LearnerSupervisionDetail(LearnerSupervisionState):
    alerts: list[SupervisionAlert] = Field(default_factory=list)


class TeacherInterventionRequest(BaseModel):
    intervention_type: TeacherInterventionType
    message: str | None = None


router = APIRouter(
    prefix="/education/supervision",
    tags=["education-supervision"],
)

_projection = LearnerSupervisionProjection()


def get_supervision_projection() -> LearnerSupervisionProjection:
    return _projection


@router.get(
    "/learners/{learner_id}/snapshot",
    response_model=LearnerSupervisionState,
)
def get_learner_snapshot(
    learner_id: UUID,
    request: Request,
    projection: LearnerSupervisionProjection = Depends(get_supervision_projection),
) -> LearnerSupervisionState:
    state = projection.get(
        tenant_id=require_uuid_tenant(request),
        learner_id=learner_id,
    )
    if state is None:
        raise HTTPException(
            status_code=404,
            detail="Learner supervision state not found.",
        )
    return state


@router.get(
    "/learners/{learner_id}/detail",
    response_model=LearnerSupervisionDetail,
)
def get_learner_detail(
    learner_id: UUID,
    request: Request,
    projection: LearnerSupervisionProjection = Depends(get_supervision_projection),
) -> LearnerSupervisionDetail:
    state = projection.get(
        tenant_id=require_uuid_tenant(request),
        learner_id=learner_id,
    )
    if state is None:
        raise HTTPException(
            status_code=404,
            detail="Learner supervision state not found.",
        )
    history = PostgresLearningEventHistory(get_database_url())
    history.initialize_schema()
    events = history.list_for_learner(
        tenant_id=state.tenant_id,
        learner_id=state.learner_id,
    )
    repeated_failures = 0
    for event in reversed(events):
        if event.event_type != EducationEventType.ANSWER_SUBMITTED:
            continue
        if event.payload.get("correct") is True:
            break
        if event.payload.get("correct") is False:
            repeated_failures += 1

    return LearnerSupervisionDetail(
        **state.model_dump(),
        alerts=alerts_for_state(state, repeated_failures=repeated_failures),
    )


@router.get("/learners/{learner_id}/history")
def get_learner_history(learner_id: UUID, request: Request):
    history = PostgresLearningEventHistory(get_database_url())
    history.initialize_schema()
    return history.list_for_learner(
        tenant_id=require_uuid_tenant(request), learner_id=learner_id
    )


@router.post("/learners/{learner_id}/replay", response_model=LearnerSupervisionState)
def replay_learner_history(
    learner_id: UUID,
    request: Request,
    projection: LearnerSupervisionProjection = Depends(get_supervision_projection),
) -> LearnerSupervisionState:
    tenant_id = require_uuid_tenant(request)
    history = PostgresLearningEventHistory(get_database_url())
    history.initialize_schema()
    events = history.list_for_learner(tenant_id=tenant_id, learner_id=learner_id)
    if not events:
        raise HTTPException(status_code=404, detail="Learner history not found.")
    state = projection.replay(
        events,
        tenant_id=tenant_id,
        learner_id=learner_id,
    )
    assert state is not None
    return state


@router.post(
    "/learners/{learner_id}/interventions",
    response_model=TeacherIntervention,
    status_code=201,
)
def create_teacher_intervention(
    learner_id: UUID,
    payload: TeacherInterventionRequest,
    request: Request,
    projection: LearnerSupervisionProjection = Depends(get_supervision_projection),
    proof_service: ProofApplicationService = Depends(get_education_proof_service),
    event_publisher: EducationEventPublisher = Depends(get_education_event_publisher),
) -> TeacherIntervention:
    tenant_id = require_uuid_tenant(request)
    state = projection.get(tenant_id=tenant_id, learner_id=learner_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Learner supervision state not found.")

    message = payload.message
    if payload.intervention_type == TeacherInterventionType.REQUEST_NEW_PROOF:
        if state.assessment_id is None:
            raise HTTPException(status_code=409, detail="No active assessment is available for a proof request.")

        history = PostgresLearningEventHistory(get_database_url())
        history.initialize_schema()
        events = history.list_for_learner(tenant_id=tenant_id, learner_id=learner_id)
        source_event = next(
            (
                event for event in reversed(events)
                if event.assessment_id == state.assessment_id
                and event.question_id is not None
                and event.competency_code
                and event.event_type in {
                    EducationEventType.ANSWER_SUBMITTED,
                    EducationEventType.MASTERY_UPDATED,
                    EducationEventType.AUTONOMY_UPDATED,
                }
            ),
            None,
        )
        if source_event is None:
            raise HTTPException(status_code=409, detail="No assessed competency is available for a proof request.")

        from rkjo_api.education_dependencies import get_education_assessment_service
        assessment = get_education_assessment_service().get_assessment(
            tenant_id=tenant_id,
            assessment_id=state.assessment_id,
        )
        verification = next(
            (
                question for question in assessment.questions
                if question.id != source_event.question_id
                and (question.competency_code or "").strip() == source_event.competency_code
            ),
            None,
        )
        if verification is None:
            raise HTTPException(
                status_code=409,
                detail="A different question testing the same competency is required for a new proof.",
            )

        try:
            challenge = proof_service.create_challenge(
                tenant_id=tenant_id,
                learner_id=learner_id,
                assessment_id=state.assessment_id,
                source_question_id=source_event.question_id,
                verification_question_id=verification.id,
            )
        except (ProofQuestionNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        event_publisher.publish(EducationLearningEvent(
            event_type=EducationEventType.PROOF_REQUESTED,
            tenant_id=tenant_id,
            learner_id=learner_id,
            course_id=state.course_id,
            assessment_id=state.assessment_id,
            question_id=source_event.question_id,
            competency_code=source_event.competency_code,
            payload={"proof_challenge_id": str(challenge.id), "requested_by": "teacher"},
        ))
        message = str(challenge.id)

    if payload.intervention_type == TeacherInterventionType.ASSIGN_CONSOLIDATION:
        if state.assessment_id is None:
            raise HTTPException(
                status_code=409,
                detail="No active assessment is available for consolidation.",
            )
        message = str(state.assessment_id)

    interventions = PostgresTeacherInterventionStore(get_database_url())
    interventions.initialize_schema()
    return interventions.create(TeacherIntervention(
        tenant_id=tenant_id,
        learner_id=learner_id,
        intervention_type=payload.intervention_type,
        message=message,
    ))


@router.get(
    "/learners/{learner_id}/interventions",
    response_model=list[TeacherIntervention],
)
def list_teacher_interventions(
    learner_id: UUID,
    request: Request,
) -> list[TeacherIntervention]:
    interventions = PostgresTeacherInterventionStore(get_database_url())
    interventions.initialize_schema()
    tenant_id = require_uuid_tenant(request)
    items = interventions.list_for_learner(
        tenant_id=tenant_id,
        learner_id=learner_id,
    )
    history = PostgresLearningEventHistory(get_database_url())
    history.initialize_schema()
    events = history.list_for_learner(tenant_id=tenant_id, learner_id=learner_id)
    completed_challenges = {
        str(event.payload.get("challenge_id") or event.payload.get("proof_challenge_id")): (
            "passed" if event.event_type == EducationEventType.PROOF_PASSED else "failed"
        )
        for event in events
        if event.event_type in {EducationEventType.PROOF_PASSED, EducationEventType.PROOF_FAILED}
        and (event.payload.get("challenge_id") or event.payload.get("proof_challenge_id"))
    }

    def completed(item: TeacherIntervention) -> bool:
        if item.intervention_type == TeacherInterventionType.REQUEST_NEW_PROOF:
            return bool(item.message and item.message in completed_challenges)
        if item.intervention_type == TeacherInterventionType.ASSIGN_CONSOLIDATION:
            return any(
                event.event_type == EducationEventType.ASSESSMENT_COMPLETED
                and event.assessment_id is not None
                and str(event.assessment_id) == item.message
                and event.occurred_at >= item.requested_at
                for event in events
            )
        return False

    enriched: list[TeacherIntervention] = []
    for item in items:
        update: dict[str, object] = {}
        if completed(item):
            update["status"] = "acknowledged"
        if item.intervention_type == TeacherInterventionType.ASSIGN_CONSOLIDATION:
            result_event = next(
                (
                    event for event in reversed(events)
                    if event.event_type == EducationEventType.ANSWER_SUBMITTED
                    and event.assessment_id is not None
                    and str(event.assessment_id) == item.message
                    and event.occurred_at >= item.requested_at
                ),
                None,
            )
            if result_event is not None:
                update["result_status"] = (
                    "passed" if result_event.payload.get("correct") is True else "failed"
                )
                update["result_autonomy_score"] = next(
                    (
                        event.payload.get("autonomy_score")
                        for event in reversed(events)
                        if event.event_type == EducationEventType.AUTONOMY_UPDATED
                        and event.assessment_id == result_event.assessment_id
                        and event.question_id == result_event.question_id
                        and event.competency_code == result_event.competency_code
                        and event.occurred_at >= result_event.occurred_at
                    ),
                    None,
                )
                update["result_mastery"] = next(
                    (
                        event.payload.get("mastery")
                        for event in reversed(events)
                        if event.event_type == EducationEventType.MASTERY_UPDATED
                        and event.assessment_id == result_event.assessment_id
                        and event.question_id == result_event.question_id
                        and event.competency_code == result_event.competency_code
                        and event.occurred_at >= result_event.occurred_at
                    ),
                    None,
                )
        enriched.append(item.model_copy(update=update))
    return enriched


@router.post(
    "/learners/{learner_id}/interventions/delivered",
    response_model=list[TeacherIntervention],
)
def mark_teacher_interventions_delivered(
    learner_id: UUID,
    request: Request,
) -> list[TeacherIntervention]:
    interventions = PostgresTeacherInterventionStore(get_database_url())
    interventions.initialize_schema()
    return interventions.mark_delivered(
        tenant_id=require_uuid_tenant(request),
        learner_id=learner_id,
    )


@router.post(
    "/learners/{learner_id}/interventions/{intervention_id}/acknowledge",
    response_model=TeacherIntervention,
)
def acknowledge_teacher_intervention(
    learner_id: UUID,
    intervention_id: UUID,
    request: Request,
) -> TeacherIntervention:
    interventions = PostgresTeacherInterventionStore(get_database_url())
    interventions.initialize_schema()
    intervention = interventions.acknowledge(
        tenant_id=require_uuid_tenant(request),
        learner_id=learner_id,
        intervention_id=intervention_id,
    )
    if intervention is None:
        raise HTTPException(status_code=404, detail="Teacher intervention not found.")
    return intervention


@router.get(
    "/snapshot",
    response_model=list[LearnerSupervisionState],
)
def get_tenant_snapshot(
    request: Request,
    projection: LearnerSupervisionProjection = Depends(get_supervision_projection),
) -> list[LearnerSupervisionState]:
    return projection.list_for_tenant(
        tenant_id=require_uuid_tenant(request)
    )


async def supervision_event_stream(
    *,
    request: Request,
    tenant_id: UUID,
    projection: LearnerSupervisionProjection,
    poll_interval_seconds: float = 0.25,
):
    """Stream tenant-scoped supervision snapshots when their state changes."""
    last_version: tuple[tuple[str, str], ...] | None = None

    while not await request.is_disconnected():
        states = projection.list_for_tenant(tenant_id=tenant_id)
        version = tuple(
            (str(state.learner_id), str(state.last_event_id))
            for state in states
        )

        if version != last_version:
            payload = [
                state.model_dump(mode="json")
                for state in states
            ]
            yield "event: supervision.snapshot\n"
            yield f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
            last_version = version

        await asyncio.sleep(poll_interval_seconds)


@router.get("/stream")
def stream_tenant_supervision(
    request: Request,
    projection: LearnerSupervisionProjection = Depends(get_supervision_projection),
):
    tenant_id = require_uuid_tenant(request)
    return StreamingResponse(
        supervision_event_stream(
            request=request,
            tenant_id=tenant_id,
            projection=projection,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
