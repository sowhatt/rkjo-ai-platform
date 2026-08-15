"""RAG document ingestion HTTP API."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from pydantic import BaseModel

from rkjo_api.dependencies import (
    get_rag_ingestion_pipeline,
)
from rkjo_kernel.rag.ingestion import (
    DocumentIngestionPipeline,
)


router = APIRouter(
    prefix="/rag",
    tags=["rag"],
)


MAX_UPLOAD_BYTES = (
    10 * 1024 * 1024
)

SUPPORTED_SUFFIXES = {
    ".pdf",
    ".txt",
    ".md",
    ".markdown",
}


class DocumentIngestionResponse(
    BaseModel
):
    document_id: str
    content_hash: str
    chunk_count: int
    duplicate: bool


def parse_metadata(
    raw_metadata: str | None,
) -> dict[str, Any]:
    if raw_metadata is None:
        return {}

    try:
        parsed = json.loads(
            raw_metadata
        )

    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "metadata must be valid JSON."
            ),
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "metadata must be a JSON object."
            ),
        )

    return parsed


async def persist_upload_temporarily(
    upload: UploadFile,
) -> Path:
    """Write a bounded upload to a temporary file."""

    filename = (
        upload.filename
        or "document"
    )

    suffix = Path(
        filename
    ).suffix.lower()

    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported document format."
            ),
        )

    total_bytes = 0

    temporary = (
        NamedTemporaryFile(
            mode="wb",
            suffix=suffix,
            delete=False,
        )
    )

    temporary_path = Path(
        temporary.name
    )

    try:
        while True:
            chunk = await upload.read(
                1024 * 1024
            )

            if not chunk:
                break

            total_bytes += len(
                chunk
            )

            if (
                total_bytes
                > MAX_UPLOAD_BYTES
            ):
                raise HTTPException(
                    status_code=413,
                    detail=(
                        "Document exceeds "
                        "maximum upload size."
                    ),
                )

            temporary.write(
                chunk
            )

    except Exception:
        temporary.close()

        temporary_path.unlink(
            missing_ok=True
        )

        raise

    finally:
        await upload.close()

    temporary.close()

    if total_bytes == 0:
        temporary_path.unlink(
            missing_ok=True
        )

        raise HTTPException(
            status_code=422,
            detail=(
                "Uploaded document is empty."
            ),
        )

    return temporary_path


@router.post(
    "/documents",
    response_model=DocumentIngestionResponse,
    status_code=201,
)
async def ingest_document(
    response: Response,
    file: UploadFile = File(...),
    document_id: str | None = Form(
        default=None
    ),
    metadata: str | None = Form(
        default=None
    ),
    pipeline: DocumentIngestionPipeline = Depends(
        get_rag_ingestion_pipeline
    ),
) -> DocumentIngestionResponse:
    parsed_metadata = parse_metadata(
        metadata
    )

    temporary_path = (
        await persist_upload_temporarily(
            file
        )
    )

    try:
        result = pipeline.ingest_file(
            temporary_path,
            document_id=document_id,
            metadata={
                **parsed_metadata,
                "original_filename": (
                    file.filename
                    or ""
                ),
            },
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    finally:
        temporary_path.unlink(
            missing_ok=True
        )

    if result.duplicate:
        response.status_code = 200

    return DocumentIngestionResponse(
        document_id=result.document_id,
        content_hash=result.content_hash,
        chunk_count=result.chunk_count,
        duplicate=result.duplicate,
    )
