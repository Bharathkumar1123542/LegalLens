"""
Documents routes — LegalLens API v1 (Phase 1 scope)
Implements: architecture.md §8 /documents/* endpoints (Phase 1 subset).
  POST   /documents                        → 202 UploadAccepted
  GET    /documents/{document_id}          → 200 DocumentResponse
  GET    /documents/{document_id}/status   → 200 DocumentStatusResponse
  DELETE /documents/{document_id}          → 204

code-standards.md §Authorization:
  - Every resource-scoped endpoint checks owner_id before returning/mutating data.
  - A second user's token must receive 403/404, never the resource.
  - Ownership check is not optional on any endpoint (enforced in _get_owned_doc helper).

architecture.md §3 step 1:
  POST /documents validates MIME/size, stores to S3, creates Document row
  (status=uploaded), enqueues ingestion, returns 202.

Phase 8: Enhanced file validation and rate limiting applied
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Request, UploadFile, File, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.core.rate_limiter import limiter, RateLimits
from app.db.session import get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentStatusResponse, UploadAccepted
from app.schemas.simplification import SimplifyRequest, SimplificationResponse, CitationResponse
from app.schemas.clause import (
    ExtractClausesRequest,
    ExtractClausesAccepted,
    ClauseResponse,
    ClausesListResponse,
)
from app.services import ingestion as ingestion_service
from app.services.audit import record_audit_event
from app.services.simplification import simplify_document
from app.services.storage import delete_from_s3
from app.workers.extraction_worker import extract_clauses_task
from app.models.clause import Clause
from typing import Annotated

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


async def _get_owned_doc(
    document_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> Document:
    """
    Fetch a Document row, enforcing ownership.
    Returns 404 (not 403) when the document exists but belongs to another user —
    avoids confirming resource existence to unauthorised callers.
    code-standards.md §Authorization: mandatory on every resource-scoped endpoint.
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc: Document | None = result.scalar_one_or_none()

    if doc is None or doc.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return doc


@router.post(
    "",
    response_model=UploadAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for processing",
)
@limiter.limit(RateLimits.DOCUMENT_UPLOAD)
async def upload_document(
    request: Request,
    file: Annotated[UploadFile, File(description="PDF, DOCX, or plain-text file (≤ 50 MB)")],
    current_user: CurrentUser,
    db: DbDep,
) -> UploadAccepted:
    ip = request.client.host if request.client else "unknown"
    document = await ingestion_service.create_document(
        owner_id=current_user.id,
        file=file,
        db=db,
        ip_address=ip,
    )
    await db.commit()
    return UploadAccepted.model_validate(document)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch document metadata",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> DocumentResponse:
    doc = await _get_owned_doc(document_id, current_user, db)
    return DocumentResponse.model_validate(doc)


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Poll ingestion status",
)
async def get_document_status(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> DocumentStatusResponse:
    doc = await _get_owned_doc(document_id, current_user, db)
    return DocumentStatusResponse.model_validate(doc)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hard-delete a document and all derived data",
)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
) -> None:
    doc = await _get_owned_doc(document_id, current_user, db)
    ip = request.client.host if request.client else "unknown"

    # Delete from S3 first — if this fails, the DB row is not deleted
    await delete_from_s3(doc.storage_key)

    # Audit before deleting the DB row (so resource_id still refers to a real row)
    await record_audit_event(
        db=db,
        actor_id=current_user.id,
        action="document.delete",
        resource_type="document",
        resource_id=doc.id,
        metadata={"original_filename": doc.original_filename},
        ip_address=ip,
    )

    await db.delete(doc)
    await db.commit()



@router.post(
    "/{document_id}/simplify",
    response_model=SimplificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate plain-language simplification of a document",
    responses={
        409: {"description": "Document not ready (still processing)"},
        502: {"description": "LLM service error"},
    },
)
async def simplify_document_endpoint(
    document_id: uuid.UUID,
    request_body: SimplifyRequest,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
) -> SimplificationResponse:
    """
    Simplify a document to the specified reading level.
    
    Per architecture.md §3 step 5:
    - Small documents (≤5 chunks): single-pass simplification
    - Large documents (>5 chunks): map-reduce with coherence pass
    
    Returns simplified text with citations to source chunks.
    
    **Note:** This endpoint returns the complete result. For streaming,
    use `Accept: text/event-stream` header (SSE streaming - future enhancement).
    """
    # Verify document ownership and readiness
    doc = await _get_owned_doc(document_id, current_user, db)
    
    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document status is '{doc.status}'. Must be 'ready' to simplify.",
        )
    
    # Audit the simplification request
    ip = request.client.host if request.client else "unknown"
    await record_audit_event(
        db=db,
        actor_id=current_user.id,
        action="document.simplify",
        resource_type="document",
        resource_id=document_id,
        metadata={
            "reading_level": request_body.reading_level,
            "scope": request_body.scope,
        },
        ip_address=ip,
    )
    
    try:
        # Call simplification service
        log.info(
            "simplification.request",
            document_id=str(document_id),
            reading_level=request_body.reading_level,
            user_id=str(current_user.id),
        )
        
        result = await simplify_document(
            db=db,
            document_id=document_id,
            reading_level=request_body.reading_level,
        )
        
        log.info(
            "simplification.success",
            document_id=str(document_id),
            citations=len(result.citations),
            content_length=len(result.simplified_text),
        )
        
        # Convert to response schema
        return SimplificationResponse(
            document_id=result.document_id,
            simplified_text=result.simplified_text,
            reading_level=result.reading_level,
            citations=[
                CitationResponse(
                    chunk_id=citation.chunk_id,
                    page_number=citation.page_number,
                    excerpt=citation.excerpt,
                )
                for citation in result.citations
            ],
            chunk_count=result.chunk_count,
        )
        
    except ValueError as e:
        # LLM generation or validation error
        log.error(
            "simplification.failed",
            document_id=str(document_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Simplification failed: {str(e)}",
        ) from e
    
    except Exception as e:
        log.error(
            "simplification.unexpected_error",
            document_id=str(document_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during simplification.",
        ) from e



@router.post(
    "/{document_id}/extract-clauses",
    response_model=ExtractClausesAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Extract and classify clauses from a document",
    responses={
        409: {"description": "Document not ready (still processing)"},
    },
)
async def extract_clauses_endpoint(
    document_id: uuid.UUID,
    request_body: ExtractClausesRequest,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
) -> ExtractClausesAccepted:
    """
    Extract clauses from a document with risk assessment.
    
    Per architecture.md §6.5:
    - Hybrid approach: keyword pre-filter + LLM classification
    - Uses claude-haiku for efficient classification
    - Runs asynchronously (returns 202 immediately)
    
    Clause types extracted (default all except 'other'):
    - indemnification, termination, limitation_of_liability
    - confidentiality, non_compete, arbitration_dispute_resolution
    - payment_terms, auto_renewal, governing_law
    
    Poll GET /documents/{id}/clauses to retrieve results.
    """
    # Verify document ownership and readiness
    doc = await _get_owned_doc(document_id, current_user, db)
    
    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document status is '{doc.status}'. Must be 'ready' to extract clauses.",
        )
    
    # Audit the extraction request
    ip = request.client.host if request.client else "unknown"
    await record_audit_event(
        db=db,
        actor_id=current_user.id,
        action="document.extract_clauses",
        resource_type="document",
        resource_id=document_id,
        metadata={"clause_types": request_body.clause_types},
        ip_address=ip,
    )
    
    # Enqueue async extraction task
    log.info(
        "clause_extraction.enqueue",
        document_id=str(document_id),
        clause_types=request_body.clause_types,
        user_id=str(current_user.id),
    )
    
    extract_clauses_task.delay(
        document_id=str(document_id),
        clause_types=request_body.clause_types,
    )
    
    return ExtractClausesAccepted(
        document_id=document_id,
        clause_types=request_body.clause_types,
    )


@router.get(
    "/{document_id}/clauses",
    response_model=ClausesListResponse,
    status_code=status.HTTP_200_OK,
    summary="List extracted clauses for a document",
)
async def get_clauses_endpoint(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
    clause_type: str | None = None,
    risk_level: str | None = None,
) -> ClausesListResponse:
    """
    Retrieve extracted clauses for a document.
    
    Optional filters:
    - clause_type: Filter by specific clause type
    - risk_level: Filter by risk level (low, medium, high)
    
    Returns clauses with risk assessments and aggregated statistics.
    """
    # Verify document ownership
    await _get_owned_doc(document_id, current_user, db)
    
    # Build query with optional filters
    stmt = select(Clause).where(Clause.document_id == document_id)
    
    if clause_type:
        stmt = stmt.where(Clause.clause_type == clause_type)
    
    if risk_level:
        stmt = stmt.where(Clause.risk_level == risk_level)
    
    stmt = stmt.order_by(Clause.clause_type, Clause.risk_level.desc())
    
    result = await db.execute(stmt)
    clauses = result.scalars().all()
    
    # Build response with statistics
    clause_responses = [ClauseResponse.model_validate(c) for c in clauses]
    
    # Count by type and risk
    by_type: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    
    for clause in clauses:
        by_type[clause.clause_type] = by_type.get(clause.clause_type, 0) + 1
        by_risk[clause.risk_level] = by_risk.get(clause.risk_level, 0) + 1
    
    log.info(
        "clauses.retrieved",
        document_id=str(document_id),
        total=len(clauses),
        filters={"clause_type": clause_type, "risk_level": risk_level},
    )
    
    return ClausesListResponse(
        document_id=document_id,
        clauses=clause_responses,
        total=len(clauses),
        by_type=by_type,
        by_risk=by_risk,
    )
