"""Authenticated LexIA legal-review endpoints.

No publishing, verified-status change, source ingestion or trust promotion.
Tenant and reviewer identity are taken only from the verified API middleware.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from rkjo_api.dependencies import get_database_url
from rkjo_api.identity import get_authenticated_identity
from rkjo_api.security import ApiRole
from rkjo_kernel.rag.postgres_legal_review import PostgresLegalReviewInbox
from rkjo_kernel.rag.legal_four_eyes import LegalFourEyesWorkflow


router = APIRouter(prefix="/rag/lexia/review", tags=["lexia-review"])


def get_legal_review_inbox() -> PostgresLegalReviewInbox:
    # Initialized as part of a controlled deployment/migration, not on
    # every request. No automatic schema creation from HTTP handlers.
    return PostgresLegalReviewInbox(database_url=get_database_url())


def get_legal_four_eyes_workflow() -> LegalFourEyesWorkflow:
    # Schema is deployed by administrator, never auto-created over HTTP.
    return LegalFourEyesWorkflow(database_url=get_database_url())


def require_reviewer(request: Request) -> tuple[str, str]:
    identity = get_authenticated_identity(request)
    if identity.role not in (ApiRole.OPERATOR, ApiRole.ADMIN):
        raise HTTPException(status_code=403, detail="Reviewer privileges required.")
    if not identity.tenant_id or not identity.tenant_id.strip():
        raise HTTPException(status_code=403, detail="Tenant-bound identity required.")
    if not identity.subject or not identity.subject.strip():
        # API keys have no verifiable individual actor; require JWT identity.
        raise HTTPException(status_code=403, detail="Individual reviewer identity required.")
    return identity.tenant_id, identity.subject


class ReviewActionRequest(BaseModel):
    action: str = Field(pattern="^(review_requested|review_note|rejected)$")
    note: str = Field(min_length=1, max_length=4000)


class ReviewEventResponse(BaseModel):
    packet_id: UUID
    action: str
    actor_id: str
    note: str
    occurred_at: str


@router.get("/{packet_id}/events", response_model=list[ReviewEventResponse])
def list_review_events(
    packet_id: UUID,
    request: Request,
    inbox: PostgresLegalReviewInbox = Depends(get_legal_review_inbox),
) -> list[ReviewEventResponse]:
    tenant_id, _ = require_reviewer(request)
    events = inbox.list_review_events(packet_id=packet_id, tenant_id=tenant_id)
    if not events:
        raise HTTPException(status_code=404, detail="Review packet not found.")
    return [
        ReviewEventResponse(
            packet_id=event.packet_id,
            action=event.action,
            actor_id=event.actor_id,
            note=event.note,
            occurred_at=event.occurred_at.isoformat(),
        )
        for event in events
    ]


@router.post("/{packet_id}/events", status_code=201)
def append_review_event(
    packet_id: UUID,
    payload: ReviewActionRequest,
    request: Request,
    inbox: PostgresLegalReviewInbox = Depends(get_legal_review_inbox),
) -> dict[str, str]:
    tenant_id, subject = require_reviewer(request)
    found = inbox.append_review_event(
        packet_id=packet_id,
        tenant_id=tenant_id,
        actor_id=subject,
        action=payload.action,
        note=payload.note,
    )
    if not found:
        raise HTTPException(status_code=404, detail="Review packet not found.")
    return {"status": "recorded", "packet_id": str(packet_id)}


class FourEyesVerificationRequest(BaseModel):
    dossier_id: str = Field(min_length=1, max_length=255)
    note: str = Field(min_length=1, max_length=4000)


class FourEyesVerificationResponse(BaseModel):
    state: str
    reviewer_count: int
    publishable: bool


@router.post("/{packet_id}/verify", response_model=FourEyesVerificationResponse)
def verify_legal_packet(
    packet_id: UUID,
    payload: FourEyesVerificationRequest,
    request: Request,
    workflow: LegalFourEyesWorkflow = Depends(get_legal_four_eyes_workflow),
) -> FourEyesVerificationResponse:
    """Two distinct authorized people may review; NEVER approve publication."""
    tenant_id, actor_id = require_reviewer(request)
    try:
        result = workflow.verify(
            packet_id=packet_id, tenant_id=tenant_id,
            dossier_id=payload.dossier_id, actor_id=actor_id, note=payload.note,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Legal review not permitted.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid review input.") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Review packet not found.")
    return FourEyesVerificationResponse(
        state=result.state,
        reviewer_count=result.reviewer_count,
        publishable=False,
    )
