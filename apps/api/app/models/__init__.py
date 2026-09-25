"""
ORM Models — LegalLens
All SQLAlchemy models for Alembic auto-discovery.
"""

from app.models.audit_log import AuditLog
from app.models.chat import ChatSession, ChatMessage
from app.models.clause import Clause
from app.models.comparison import ComparisonJob, ComparisonJobDocument, ComparisonResult
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.export import ExportArtifact
from app.models.user import User

__all__ = [
    "AuditLog",
    "ChatSession",
    "ChatMessage",
    "Clause",
    "ComparisonJob",
    "ComparisonJobDocument",
    "ComparisonResult",
    "Document",
    "DocumentChunk",
    "ExportArtifact",
    "User",
]
