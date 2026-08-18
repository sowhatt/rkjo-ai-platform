"""RAG document ingestion HTTP API."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from pydantic import BaseModel, Field

from rkjo_api.dependencies import (
    get_rag_answering_service,
    get_rag_document_lifecycle_service,
    get_rag_document_replacement_service,
    get_rag_document_version_history_service,
    get_rag_ingestion_pipeline,
    get_rag_search_service,
)
from rkjo_api.rag_filters import (
    RAGMetadataFilters,
)
from rkjo_api.identity import (
    bind_identity_metadata_tenant,
    bind_identity_tenant,
    get_authenticated_identity,
)
from rkjo_kernel.rag.ingestion import (
    DocumentIngestionPipeline,
)
from rkjo_kernel.rag.document_lifecycle import (
    DocumentLifecycleService,
)
from rkjo_kernel.rag.document_replacement import (
    DocumentReplacementService,
)
from rkjo_kernel.rag.document_version_history import (
    DocumentVersionHistoryService,
)
from rkjo_kernel.rag.semantic_search import (
    SemanticSearchService,
)
from rkjo_kernel.rag.rag_answering import (
    RAGAnsweringService,
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





class DocumentDeletionResponse(BaseModel):
    document_id: str
    deleted_chunk_count: int
    deleted_hash_count: int





class DocumentReplacementResponse(BaseModel):
    document_id: str
    old_deleted_chunk_count: int
    old_deleted_hash_count: int
    content_hash: str
    chunk_count: int





class DocumentVersionItemResponse(BaseModel):
    version_id: str
    version_number: int
    content_hash: str
    created_at: datetime


class DocumentVersionHistoryResponse(BaseModel):
    document_id: str
    current_version: int
    versions: list[
        DocumentVersionItemResponse
    ]


class SemanticSearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=4000,
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )
    filters: RAGMetadataFilters | None = None


class SemanticSearchItemResponse(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any]


class SemanticSearchApiResponse(BaseModel):
    sanitized_query: str
    result_count: int
    results: list[
        SemanticSearchItemResponse
    ]



class RAGAnswerRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=4000,
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )
    filters: RAGMetadataFilters | None = None


class RAGAnswerSourceResponse(BaseModel):
    citation: int
    document_id: str
    chunk_id: str
    score: float


class RAGAnswerApiResponse(BaseModel):
    answer: str
    sanitized_query: str
    sources: list[RAGAnswerSourceResponse]

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
    http_request: Request,
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

    identity = get_authenticated_identity(
        http_request
    )

    parsed_metadata = (
        bind_identity_metadata_tenant(
            identity=identity,
            metadata=parsed_metadata,
        )
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











@router.get(
    "/documents/{document_id}/versions",
    response_model=DocumentVersionHistoryResponse,
)
def get_document_versions(
    document_id: str,
    http_request: Request,
    service: DocumentVersionHistoryService = Depends(
        get_rag_document_version_history_service
    ),
) -> DocumentVersionHistoryResponse:
    """Return tenant-scoped document version history."""

    identity = get_authenticated_identity(
        http_request
    )

    tenant_id = identity.tenant_id

    # Version registry is tenant-keyed.
    # Unbound identities cannot enumerate it.
    if tenant_id is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    try:
        history = service.get_history(
            document_id=document_id,
            tenant_id=tenant_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    # Missing and cross-tenant documents are
    # deliberately indistinguishable.
    if history is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return DocumentVersionHistoryResponse(
        document_id=history.document_id,
        current_version=(
            history.current_version
        ),
        versions=[
            DocumentVersionItemResponse(
                version_id=(
                    version.version_id
                ),
                version_number=(
                    version.version_number
                ),
                content_hash=(
                    version.content_hash
                ),
                created_at=(
                    version.created_at
                ),
            )
            for version in history.versions
        ],
    )


@router.put(
    "/documents/{document_id}",
    response_model=DocumentReplacementResponse,
)
async def replace_document(
    document_id: str,
    http_request: Request,
    file: UploadFile = File(...),
    metadata: str | None = Form(
        default=None
    ),
    service: DocumentReplacementService = Depends(
        get_rag_document_replacement_service
    ),
) -> DocumentReplacementResponse:
    """Replace and reindex one tenant-scoped document."""

    parsed_metadata = parse_metadata(
        metadata
    )

    identity = get_authenticated_identity(
        http_request
    )

    parsed_metadata = (
        bind_identity_metadata_tenant(
            identity=identity,
            metadata=parsed_metadata,
        )
    )

    filters = bind_identity_tenant(
        identity=identity,
        filters=None,
    )

    temporary_path = (
        await persist_upload_temporarily(
            file
        )
    )

    try:
        result = service.replace_document(
            document_id,
            temporary_path,
            metadata={
                **parsed_metadata,
                "original_filename": (
                    file.filename
                    or ""
                ),
            },
            filters=filters,
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

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return DocumentReplacementResponse(
        document_id=result.document_id,
        old_deleted_chunk_count=(
            result.old_deleted_chunk_count
        ),
        old_deleted_hash_count=(
            result.old_deleted_hash_count
        ),
        content_hash=result.content_hash,
        chunk_count=result.chunk_count,
    )


@router.delete(
    "/documents/{document_id}",
    response_model=DocumentDeletionResponse,
)
def delete_document(
    document_id: str,
    http_request: Request,
    service: DocumentLifecycleService = Depends(
        get_rag_document_lifecycle_service
    ),
) -> DocumentDeletionResponse:
    """Delete one document inside the authenticated tenant scope."""

    identity = get_authenticated_identity(
        http_request
    )

    filters = bind_identity_tenant(
        identity=identity,
        filters=None,
    )

    try:
        result = service.delete_document(
            document_id,
            filters=filters,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    # Deliberately return 404 both for a truly missing
    # document and for a document outside the tenant scope.
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return DocumentDeletionResponse(
        document_id=result.document_id,
        deleted_chunk_count=(
            result.deleted_chunk_count
        ),
        deleted_hash_count=(
            result.deleted_hash_count
        ),
    )


@router.post(
    "/search",
    response_model=SemanticSearchApiResponse,
)
def semantic_search(
    request: SemanticSearchRequest,
    http_request: Request,
    service: SemanticSearchService = Depends(
        get_rag_search_service
    ),
) -> SemanticSearchApiResponse:
    """Search sanitized knowledge using vector similarity."""

    try:
        filters = (
            request.filters.to_retrieval_filters()
            if request.filters is not None
            else None
        )

        identity = get_authenticated_identity(
            http_request
        )

        filters = bind_identity_tenant(
            identity=identity,
            filters=filters,
        )

        result = service.search(
            request.query,
            limit=request.limit,
            filters=filters,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return SemanticSearchApiResponse(
        sanitized_query=(
            result.sanitized_query
        ),
        result_count=(
            result.result_count
        ),
        results=[
            SemanticSearchItemResponse(
                chunk_id=item.chunk_id,
                document_id=(
                    item.document_id
                ),
                content=item.content,
                score=item.score,
                metadata=item.metadata,
            )
            for item in result.results
        ],
    )


@router.post(
    "/answer",
    response_model=RAGAnswerApiResponse,
)
def rag_answer(
    request: RAGAnswerRequest,
    http_request: Request,
    service: RAGAnsweringService = Depends(
        get_rag_answering_service
    ),
) -> RAGAnswerApiResponse:
    """Generate a grounded answer with explicit source citations."""

    try:
        filters = (
            request.filters.to_retrieval_filters()
            if request.filters is not None
            else None
        )

        identity = get_authenticated_identity(
            http_request
        )

        filters = bind_identity_tenant(
            identity=identity,
            filters=filters,
        )

        result = service.answer(
            request.question,
            limit=request.limit,
            filters=filters,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return RAGAnswerApiResponse(
        answer=result.answer,
        sanitized_query=result.sanitized_query,
        sources=[
            RAGAnswerSourceResponse(
                citation=source.citation,
                document_id=source.document_id,
                chunk_id=source.chunk_id,
                score=source.score,
            )
            for source in result.sources
        ],
    )
