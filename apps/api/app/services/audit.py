"""
Audit logging service — LegalLens
Implements: architecture.md §3 step 10, §7.2 audit_logs schema.
code-standards.md §Security:
  - Every document upload, export, deletion, and LLM call writes a row here.
  - Application DB role has NO UPDATE/DELETE grant on audit_logs (enforced in migration).
  - Never raises on failure — logs the error and continues (audit failure must not
    break the primary request path, but IS logged for ops visibility).
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

log = structlog.get_logger(__name__)


async def record_audit_event(
    db: AsyncSession,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    metadata: dict,
    ip_address: str = "unknown",
) -> None:
    """
    Append an immutable audit log row.
    Must be called within an active transaction (caller commits).
    Never raises — a logging failure must not fail the primary operation.
    """
    try:
        entry = AuditLog(
            id=uuid.uuid4(),
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_=metadata,
            ip_address=ip_address if ip_address != "unknown" else None,
        )
        db.add(entry)
        await db.flush()
    except Exception as exc:  # noqa: BLE001 — intentionally broad
        log.error(
            "audit.write_failed",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            error=str(exc),
        )
