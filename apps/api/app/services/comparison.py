"""
Comparison service — LegalLens Phase 5
Implements: architecture.md §5.6 Comparison Engine Module.
Functions: create_comparison_job(), run_comparison() with clause alignment.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comparison import ComparisonJob, ComparisonJobDocument, ComparisonResult
from app.models.document import Document
from app.models.clause import Clause
from app.services.llm_orchestration import AsyncAnthropic
from app.core.config import settings

logger = logging.getLogger(__name__)


async def create_comparison_job(
    db: AsyncSession,
    owner_id: uuid.UUID,
    document_ids: list[uuid.UUID],
) -> ComparisonJob:
    """
    Create a comparison job for 2-5 documents.
    
    Per architecture.md §5.6:
    - Validates 2 ≤ document count ≤ 5
    - Verifies all documents exist, are owned by user, and status=ready
    - Creates ComparisonJob and ComparisonJobDocument records
    
    Args:
        db: Database session
        owner_id: User ID
        document_ids: List of 2-5 document UUIDs
    
    Returns:
        Created ComparisonJob
    
    Raises:
        ValueError: If validation fails
    """
    # Validate count (2-5 documents)
    if len(document_ids) < 2:
        raise ValueError("Comparison requires at least 2 documents")
    
    if len(document_ids) > 5:
        raise ValueError("Comparison supports maximum 5 documents")
    
    # Verify all documents exist, are owned, and ready
    for doc_id in document_ids:
        result = await db.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise ValueError(f"Document {doc_id} not found")
        
        if doc.owner_id != owner_id:
            raise ValueError(f"Document {doc_id} not owned by user")
        
        if doc.status != "ready":
            raise ValueError(
                f"Document {doc_id} status is '{doc.status}'. "
                f"All documents must be 'ready' for comparison."
            )
    
    # Create comparison job
    job = ComparisonJob(
        owner_id=owner_id,
        status="queued",
    )
    db.add(job)
    await db.flush()
    
    # Create document associations
    for order, doc_id in enumerate(document_ids):
        job_doc = ComparisonJobDocument(
            comparison_job_id=job.id,
            document_id=doc_id,
            document_order=order,
        )
        db.add(job_doc)
    
    await db.commit()
    await db.refresh(job)
    
    logger.info(
        f"comparison_job.created: job={job.id}, owner={owner_id}, "
        f"documents={len(document_ids)}"
    )
    
    return job


async def run_comparison(
    db: AsyncSession,
    comparison_job_id: uuid.UUID,
) -> dict:
    """
    Run clause-aligned comparison across documents.
    
    Per architecture.md §5.6:
    - Aligns clauses by clause_type across input documents
    - Calls Claude to generate diff summary and materiality rating
    - Persists ComparisonResult rows
    
    Args:
        db: Database session
        comparison_job_id: Comparison job ID
    
    Returns:
        Dict with comparison statistics
    
    Raises:
        ValueError: If job not found or documents not ready
    """
    # Get comparison job
    result = await db.execute(
        select(ComparisonJob).where(ComparisonJob.id == comparison_job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise ValueError(f"Comparison job {comparison_job_id} not found")
    
    # Update status to running
    job.status = "running"
    await db.commit()
    
    try:
        # Get associated documents
        job_docs_result = await db.execute(
            select(ComparisonJobDocument)
            .where(ComparisonJobDocument.comparison_job_id == comparison_job_id)
            .order_by(ComparisonJobDocument.document_order)
        )
        job_docs = job_docs_result.scalars().all()
        document_ids = [jd.document_id for jd in job_docs]
        
        logger.info(
            f"comparison.run: job={comparison_job_id}, "
            f"documents={len(document_ids)}"
        )
        
        # Get all clauses for all documents
        clauses_result = await db.execute(
            select(Clause).where(Clause.document_id.in_(document_ids))
        )
        all_clauses = clauses_result.scalars().all()
        
        # Group clauses by type
        clauses_by_type = {}
        for clause in all_clauses:
            if clause.clause_type not in clauses_by_type:
                clauses_by_type[clause.clause_type] = []
            clauses_by_type[clause.clause_type].append(clause)
        
        logger.info(
            f"comparison.grouped: job={comparison_job_id}, "
            f"clause_types={len(clauses_by_type)}"
        )
        
        # Compare each clause type
        results_count = 0
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        for clause_type, clauses in clauses_by_type.items():
            # Group by document
            excerpts_by_doc = {}
            for clause in clauses:
                doc_id_str = str(clause.document_id)
                if doc_id_str not in excerpts_by_doc:
                    excerpts_by_doc[doc_id_str] = []
                excerpts_by_doc[doc_id_str].append(clause.text_excerpt)
            
            # Skip if only one document has this clause type
            if len(excerpts_by_doc) < 2:
                logger.info(
                    f"comparison.skip: job={comparison_job_id}, "
                    f"clause_type={clause_type}, reason=single_document"
                )
                continue
            
            # Combine excerpts per document
            excerpts_combined = {
                doc_id: " ".join(excerpts)
                for doc_id, excerpts in excerpts_by_doc.items()
            }
            
            # Build prompt
            excerpts_text = "\n\n".join([
                f"**Document {i+1} ({doc_id})**:\n{text}"
                for i, (doc_id, text) in enumerate(excerpts_combined.items())
            ])
            
            prompt = f"""Compare the following {clause_type} clauses across documents.

{excerpts_text}

Return a JSON object with:
- clause_type: "{clause_type}"
- excerpts_by_document: object mapping document IDs to excerpts
- diff_summary: 2-3 sentence explanation of key differences
- materiality: one of (none, minor, significant, critical)
"""
            
            try:
                # Call Claude for comparison
                message = await client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                
                response_text = message.content[0].text
                
                # Parse JSON response
                try:
                    # Extract JSON if wrapped in code blocks
                    if "```json" in response_text:
                        json_start = response_text.find("```json") + 7
                        json_end = response_text.find("```", json_start)
                        json_text = response_text[json_start:json_end].strip()
                    else:
                        json_text = response_text
                    
                    comparison_data = json.loads(json_text)
                    
                    # Create comparison result
                    result_obj = ComparisonResult(
                        comparison_job_id=comparison_job_id,
                        clause_type=clause_type,
                        excerpts_by_document=excerpts_combined,
                        diff_summary=comparison_data.get("diff_summary", ""),
                        materiality=comparison_data.get("materiality", "none"),
                    )
                    db.add(result_obj)
                    results_count += 1
                    
                    logger.info(
                        f"comparison.result: job={comparison_job_id}, "
                        f"clause_type={clause_type}, "
                        f"materiality={comparison_data.get('materiality')}"
                    )
                    
                except json.JSONDecodeError as e:
                    logger.error(
                        f"comparison.parse_error: job={comparison_job_id}, "
                        f"clause_type={clause_type}, error={e}"
                    )
                    continue
                
            except Exception as e:
                logger.error(
                    f"comparison.llm_error: job={comparison_job_id}, "
                    f"clause_type={clause_type}, error={e}"
                )
                continue
        
        # Update job status
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        
        logger.info(
            f"comparison.completed: job={comparison_job_id}, "
            f"results={results_count}"
        )
        
        return {
            "comparison_job_id": str(comparison_job_id),
            "results_count": results_count,
        }
        
    except Exception as e:
        # Update job status to failed
        job.status = "failed"
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        
        logger.error(f"comparison.failed: job={comparison_job_id}, error={e}")
        raise
