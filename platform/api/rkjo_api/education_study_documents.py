"""Authenticated, stateless PDF course preview for education students.

No persistence or LLM transfer. A bearer identity with tenant and subject is
mandatory even when RKJO's global API-key middleware accepted the request.
"""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from rkjo_education.curriculum.health_study_generator import make_revision_outline
from rkjo_education.curriculum.study_learning_views import build_study_views
from rkjo_education.curriculum.pdf_study_ingest import StudyPdfError, extract_study_pdf
from rkjo_education.curriculum.study_sources import StudyDocumentType

router = APIRouter(prefix="/education/study", tags=["education-study"])
MAX_PDF_BYTES = 15 * 1024 * 1024


@router.post("/preview-pdf")
async def preview_course_pdf(
    request: Request,
    file: UploadFile = File(...),
    programme_id: str = Form(..., min_length=1, max_length=120),
    ue_id: str = Form(..., min_length=1, max_length=120),
    document_type: StudyDocumentType = Form(StudyDocumentType.CM),
) -> dict[str, object]:
    # Global middleware validates Bearer signature, expiry and RBAC. API keys
    # cannot impersonate students here because they do not carry a subject.
    tenant = getattr(request.state, "api_tenant_id", None)
    subject = getattr(request.state, "api_subject", None)
    if not subject or not tenant or not request.headers.get("authorization", "").startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Individual tenant-bound Bearer identity required")
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="PDF content type required")
    try:
        data = await file.read(MAX_PDF_BYTES + 1)
        if len(data) > MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="PDF too large")
        document_id = str(uuid4())
        source = extract_study_pdf(
            pdf_bytes=data,
            tenant_id=str(tenant),
            learner_id=str(subject),
            programme_id=programme_id,
            ue_id=ue_id,
            document_id=document_id,
            document_type=document_type,
        )
        outline = make_revision_outline(source)
        views = build_study_views(source)
    except StudyPdfError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
    return {
        "document_id": source.document_id,
        "ue_id": source.ue_id,
        "document_type": source.document_type.value,
        "pages_with_text": len(source.segments),
        "preview_only": True,
        **views,
        "revision_outline": [
            {
                "title": item.title,
                "body": item.body,
                "pages": [source.segment(ref).page for ref in item.segment_ids],
            }
            for item in outline.items[:20]
        ],
    }
