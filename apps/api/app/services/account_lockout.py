"""
Account Lockout Service — Phase 9
Implements protection against brute force attacks.

Strategy:
- Track failed login attempts per user
- Lock account after 5 consecutive failures
- Lockout duration: 15 minutes
- Reset counter on successful login
- Admin can manually unlock accounts

Security:
- Lockout applies to all login attempts (prevents bypass)
- Time-based automatic unlock (no manual intervention required)
- Failed attempt tracking (audit trail)
- Rate limiting additional protection (handled by slowapi)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog

from app.models.user import User

log = structlog.get_logger(__name__)

# Lockout configuration
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class AccountLockoutService:
    """Service for managing account lockout after failed login attempts."""
    
    @staticmethod
    def is_locked(user: User) -> bool:
        """
        Check if account is currently locked.
        
        Args:
            user: User model instance
        
        Returns:
            True if account is locked, False otherwise
        
        Notes:
            - Checks locked_until timestamp
            - Returns False if lockout has expired
        """
        if not user.locked_until:
            return False
        
        now = datetime.now(timezone.utc)
        is_locked = user.locked_until > now
        
        if not is_locked:
            # Lockout expired, clear it
            log.info(
                "account_lockout_expired",
                user_id=str(user.id),
                locked_until=user.locked_until.isoformat(),
            )
        
        return is_locked
    
    @staticmethod
    def record_failed_login(user: User) -> tuple[bool, int, datetime | None]:
        """
        Record a failed login attempt and lock account if threshold exceeded.
        
        Args:
            user: User model instance
        
        Returns:
            Tuple of (is_now_locked, failed_attempts, locked_until)
            - is_now_locked: True if account is now locked
            - failed_attempts: Current count of failed attempts
            - locked_until: Timestamp when lockout expires (None if not locked)
        
        Notes:
            - Increments failed_login_attempts counter
            - Sets locked_until if threshold exceeded
            - Updates last_failed_login timestamp
            - Does NOT commit transaction (caller must commit)
        """
        now = datetime.now(timezone.utc)
        
        # Increment counter
        user.failed_login_attempts += 1
        user.last_failed_login = now
        
        # Check if lockout threshold exceeded
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            
            log.warning(
                "account_locked",
                user_id=str(user.id),
                failed_attempts=user.failed_login_attempts,
                locked_until=user.locked_until.isoformat(),
            )
            
            return True, user.failed_login_attempts, user.locked_until
        
        log.info(
            "failed_login_attempt",
            user_id=str(user.id),
            failed_attempts=user.failed_login_attempts,
            remaining_attempts=MAX_FAILED_ATTEMPTS - user.failed_login_attempts,
        )
        
        return False, user.failed_login_attempts, None
    
    @staticmethod
    def reset_failed_attempts(user: User) -> None:
        """
        Reset failed login attempts counter (after successful login).
        
        Args:
            user: User model instance
        
        Notes:
            - Resets failed_login_attempts to 0
            - Clears locked_until timestamp
            - Does NOT commit transaction (caller must commit)
        """
        if user.failed_login_attempts > 0 or user.locked_until:
            log.info(
                "login_attempts_reset",
                user_id=str(user.id),
                previous_attempts=user.failed_login_attempts,
            )
            
            user.failed_login_attempts = 0
            user.locked_until = None
    
    @staticmethod
    def unlock_account(user: User) -> None:
        """
        Manually unlock an account (admin action).
        
        Args:
            user: User model instance
        
        Notes:
            - Clears locked_until timestamp
            - Resets failed_login_attempts counter
            - Does NOT commit transaction (caller must commit)
        """
        log.info(
            "account_manually_unlocked",
            user_id=str(user.id),
            failed_attempts=user.failed_login_attempts,
        )
        
        user.failed_login_attempts = 0
        user.locked_until = None
    
    @staticmethod
    def get_remaining_lockout_time(user: User) -> timedelta | None:
        """
        Get remaining time until account unlock.
        
        Args:
            user: User model instance
        
        Returns:
            Timedelta until unlock, or None if not locked
        """
        if not user.locked_until:
            return None
        
        now = datetime.now(timezone.utc)
        if user.locked_until <= now:
            return None
        
        return user.locked_until - now


# Singleton instance
lockout_service = AccountLockoutService()
