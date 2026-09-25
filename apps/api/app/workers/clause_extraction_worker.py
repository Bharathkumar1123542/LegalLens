"""
Clause Extraction Celery Worker — LegalLens Phase 3
Implements: Async clause extraction per architecture.md §6.5.
Task: extract_clauses_task enqueued by POST /documents/{id}/extract-clauses.
"""

import logging
import uuid

from celery import shared_task
from sqlalchemy import select

from app.db.session import get_async_session
from app.models.clause import Clause
from app.models.document import Document
from app.services.clause_extraction import extract_clauses_from_document

logger = logging.getLogger(__name__)


@shared_task(
    name="extract_clauses_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def extract_clauses_task(
    self,
    document_id_str: str,
    clause_types: list[str],
) -> dict:
    """
    Extract clauses from a document (all specified types).
    
    Runs asynchronously via Celery. Extracts each clause type sequentially,
    persisting results to the clauses table.
    
    Args:
        document_id_str: UUID string of document
        clause_types: List of clause types to extract
    
    Returns:
        Dict with extraction results
    """
    document_id = uuid.UUID(document_id_str)
    
    logger.info(
        f"Starting clause extraction: document={document_id}, "
        f"types={clause_types}"
    )
    
    try:
        # Use async context for database operations
        import asyncio
        result = asyncio.run(
            _extract_clauses_async(document_id, clause_types)
        )
        
        logger.info(
            f"Clause extraction complete: document={document_id}, "
            f"extracted={result['total_extracted']}"
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"Clause extraction failed: document={document_id}, error={e}"
        )
        # Retry on transient failures
        raise self.retry(exc=e)


async def _extract_clauses_async(
    document_id: uuid.UUID,
    clause_types: list[str],
) -> dict:
    """
    Async implementation of clause extraction.
    
    Extracts each clause type sequentially and persists to database.
    """
    async for db in get_async_session():
        try:
            # Verify document exists and is ready
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                raise ValueError(f"Document {document_id} not found")
            
            if document.status != "ready":
                raise ValueError(
                    f"Document {document_id} status is {document.status}, "
                    f"must be 'ready' for clause extraction"
                )
            
            total_extracted = 0
            results_by_type = {}
            
            # Extract each clause type
            for clause_type in clause_types:
                try:
                    logger.info(
                        f"Extracting {clause_type} from document {document_id}"
                    )
                    
                    candidates = await extract_clauses_from_document(
                        db=db,
                        document_id=document_id,
                        clause_type=clause_type,
                    )
                    
                    # Persist extracted clauses
                    for candidate in candidates:
                        clause = Clause(
                            document_id=document_id,
                            source_chunk_id=candidate.chunk_id,
                            clause_type=candidate.clause_type,
                            text_excerpt=candidate.text_excerpt,
                            start_offset=candidate.start_offset,
                            end_offset=candidate.end_offset,
                            risk_level=candidate.risk_level,
                            risk_rationale=candidate.risk_rationale,
                        )
                        db.add(clause)
                    
                    await db.commit()
                    
                    results_by_type[clause_type] = len(candidates)
                    total_extracted += len(candidates)
                    
                    logger.info(
                        f"Extracted {len(candidates)} {clause_type} clauses"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Failed to extract {clause_type}: {e}. "
                        f"Continuing with other types."
                    )
                    await db.rollback()
                    results_by_type[clause_type] = 0
                    # Continue with other clause types
                    continue
            
            return {
                "document_id": str(document_id),
                "total_extracted": total_extracted,
                "by_type": results_by_type,
            }
            
        except Exception as e:
            await db.rollback()
            raise
        finally:
            await db.close()
