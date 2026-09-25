"""
Unit tests — services/audit.py
Tests: audit log creation, error resilience.
Covers: code-standards.md §Security (audit failure must not break primary operation).
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.audit import record_audit_event


@pytest.mark.asyncio
class TestRecordAuditEvent:
    """Test audit logging behavior."""

    async def test_record_audit_event_creates_log_entry(self):
        db = AsyncMock()
        actor_id = uuid.uuid4()
        resource_id = uuid.uuid4()
        
        await record_audit_event(
            db=db,
            actor_id=actor_id,
            action="document.upload",
            resource_type="document",
            resource_id=resource_id,
            metadata={"file_size": 1024},
            ip_address="192.0.2.1",
        )
        
        db.add.assert_called_once()
        db.flush.assert_awaited_once()
        
        # Verify the created AuditLog object
        audit_entry = db.add.call_args[0][0]
        assert audit_entry.actor_id == actor_id
        assert audit_entry.action == "document.upload"
        assert audit_entry.resource_type == "document"
        assert audit_entry.resource_id == resource_id
        assert audit_entry.metadata_ == {"file_size": 1024}
        assert audit_entry.ip_address == "192.0.2.1"

    async def test_record_audit_event_accepts_none_actor(self):
        # System actions have no actor
        db = AsyncMock()
        resource_id = uuid.uuid4()
        
        await record_audit_event(
            db=db,
            actor_id=None,
            action="system.cleanup",
            resource_type="document",
            resource_id=resource_id,
            metadata={},
            ip_address="unknown",
        )
        
        audit_entry = db.add.call_args[0][0]
        assert audit_entry.actor_id is None

    async def test_record_audit_event_handles_unknown_ip(self):
        db = AsyncMock()
        
        await record_audit_event(
            db=db,
            actor_id=uuid.uuid4(),
            action="test.action",
            resource_type="test",
            resource_id=uuid.uuid4(),
            metadata={},
            ip_address="unknown",
        )
        
        audit_entry = db.add.call_args[0][0]
        # "unknown" string should be converted to None
        assert audit_entry.ip_address is None

    async def test_record_audit_event_never_raises_on_db_error(self):
        # code-standards.md: "Never raises — a logging failure must not fail the primary operation."
        db = AsyncMock()
        db.add.side_effect = Exception("Database connection lost")
        
        # Should not raise
        await record_audit_event(
            db=db,
            actor_id=uuid.uuid4(),
            action="test.action",
            resource_type="test",
            resource_id=uuid.uuid4(),
            metadata={},
            ip_address="127.0.0.1",
        )
        
        # Verify it attempted to add but swallowed the exception
        db.add.assert_called_once()

    async def test_record_audit_event_never_raises_on_flush_error(self):
        db = AsyncMock()
        db.flush = AsyncMock(side_effect=Exception("Flush failed"))
        
        # Should not raise
        await record_audit_event(
            db=db,
            actor_id=uuid.uuid4(),
            action="test.action",
            resource_type="test",
            resource_id=uuid.uuid4(),
            metadata={},
            ip_address="127.0.0.1",
        )
        
        db.flush.assert_awaited_once()

    @patch("app.services.audit.log")
    async def test_record_audit_event_logs_error_on_failure(self, mock_log):
        # Verify that failures are logged for ops visibility
        db = AsyncMock()
        db.add.side_effect = Exception("Test error")
        
        await record_audit_event(
            db=db,
            actor_id=uuid.uuid4(),
            action="test.action",
            resource_type="test",
            resource_id=uuid.uuid4(),
            metadata={},
            ip_address="127.0.0.1",
        )
        
        # Should have called log.error
        mock_log.error.assert_called_once()
        call_kwargs = mock_log.error.call_args[1]
        assert "audit.write_failed" in call_kwargs.values()
