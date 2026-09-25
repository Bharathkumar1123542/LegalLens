"""
Unit tests for Account Lockout Service — Phase 9
Tests lockout detection, failed attempt tracking, and unlock mechanisms.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.services.account_lockout import lockout_service, MAX_FAILED_ATTEMPTS, LOCKOUT_DURATION_MINUTES
from app.models.user import User


class TestAccountLockoutService:
    """Test account lockout service functions."""
    
    def test_is_locked_not_locked(self):
        """Test account that is not locked."""
        user = MagicMock(spec=User)
        user.locked_until = None
        
        assert lockout_service.is_locked(user) is False
    
    def test_is_locked_currently_locked(self):
        """Test account that is currently locked."""
        user = MagicMock(spec=User)
        future = datetime.now(timezone.utc) + timedelta(minutes=10)
        user.locked_until = future
        
        assert lockout_service.is_locked(user) is True
    
    def test_is_locked_expired(self):
        """Test account with expired lockout."""
        user = MagicMock(spec=User)
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        user.locked_until = past
        
        # Should return False (lockout expired)
        assert lockout_service.is_locked(user) is False
    
    def test_record_failed_login_first_attempt(self):
        """Test recording first failed login attempt."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.failed_login_attempts = 0
        user.last_failed_login = None
        
        is_locked, attempts, locked_until = lockout_service.record_failed_login(user)
        
        # Should increment counter but not lock
        assert is_locked is False
        assert attempts == 1
        assert locked_until is None
        assert user.failed_login_attempts == 1
        assert user.last_failed_login is not None
    
    def test_record_failed_login_multiple_attempts(self):
        """Test recording multiple failed login attempts."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.failed_login_attempts = 3
        
        is_locked, attempts, locked_until = lockout_service.record_failed_login(user)
        
        # Should increment but not lock (4 < 5)
        assert is_locked is False
        assert attempts == 4
        assert locked_until is None
        assert user.failed_login_attempts == 4
    
    def test_record_failed_login_threshold_exceeded(self):
        """Test account lockout when threshold exceeded."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.failed_login_attempts = MAX_FAILED_ATTEMPTS - 1  # 4
        
        is_locked, attempts, locked_until = lockout_service.record_failed_login(user)
        
        # Should lock account
        assert is_locked is True
        assert attempts == MAX_FAILED_ATTEMPTS
        assert locked_until is not None
        assert user.failed_login_attempts == MAX_FAILED_ATTEMPTS
        assert user.locked_until is not None
        
        # Locked until should be ~15 minutes in future
        now = datetime.now(timezone.utc)
        time_diff = (user.locked_until - now).total_seconds() / 60
        assert 14 <= time_diff <= 16  # Allow small variance
    
    def test_record_failed_login_already_at_threshold(self):
        """Test recording failed attempt when already at threshold."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.failed_login_attempts = MAX_FAILED_ATTEMPTS
        
        is_locked, attempts, locked_until = lockout_service.record_failed_login(user)
        
        # Should lock again (extends lockout)
        assert is_locked is True
        assert attempts == MAX_FAILED_ATTEMPTS + 1
        assert locked_until is not None
    
    def test_reset_failed_attempts_with_failures(self):
        """Test resetting failed attempts counter."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.failed_login_attempts = 3
        user.locked_until = None
        
        lockout_service.reset_failed_attempts(user)
        
        # Should reset counter
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
    
    def test_reset_failed_attempts_when_locked(self):
        """Test resetting failed attempts when account is locked."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.failed_login_attempts = MAX_FAILED_ATTEMPTS
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        lockout_service.reset_failed_attempts(user)
        
        # Should reset counter and clear lockout
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
    
    def test_reset_failed_attempts_no_failures(self):
        """Test resetting when no failures recorded."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.failed_login_attempts = 0
        user.locked_until = None
        
        # Should not raise error
        lockout_service.reset_failed_attempts(user)
        
        assert user.failed_login_attempts == 0
    
    def test_unlock_account(self):
        """Test manual account unlock (admin action)."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.failed_login_attempts = MAX_FAILED_ATTEMPTS
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        lockout_service.unlock_account(user)
        
        # Should clear lockout and reset counter
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
    
    def test_get_remaining_lockout_time_not_locked(self):
        """Test getting remaining time when not locked."""
        user = MagicMock(spec=User)
        user.locked_until = None
        
        remaining = lockout_service.get_remaining_lockout_time(user)
        
        assert remaining is None
    
    def test_get_remaining_lockout_time_expired(self):
        """Test getting remaining time when lockout expired."""
        user = MagicMock(spec=User)
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        user.locked_until = past
        
        remaining = lockout_service.get_remaining_lockout_time(user)
        
        assert remaining is None
    
    def test_get_remaining_lockout_time_active(self):
        """Test getting remaining time when lockout is active."""
        user = MagicMock(spec=User)
        future = datetime.now(timezone.utc) + timedelta(minutes=10)
        user.locked_until = future
        
        remaining = lockout_service.get_remaining_lockout_time(user)
        
        assert remaining is not None
        assert isinstance(remaining, timedelta)
        # Should be approximately 10 minutes
        minutes = remaining.total_seconds() / 60
        assert 9 <= minutes <= 11  # Allow small variance
    
    def test_lockout_configuration(self):
        """Test lockout configuration constants."""
        # Verify expected values
        assert MAX_FAILED_ATTEMPTS == 5
        assert LOCKOUT_DURATION_MINUTES == 15
