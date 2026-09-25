"""Phase 9: Add account lockout fields to users table

Revision ID: 007
Revises: 006
Create Date: 2025-01-15

Adds account lockout protection against brute force attacks:
- failed_login_attempts: counter for consecutive failed logins
- locked_until: timestamp when account lockout expires
- last_failed_login: timestamp of last failed attempt
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add account lockout columns to users table
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('last_failed_login', sa.DateTime(timezone=True), nullable=True))
    
    # Index for querying locked accounts
    op.create_index('ix_users_locked_until', 'users', ['locked_until'])


def downgrade() -> None:
    op.drop_index('ix_users_locked_until', table_name='users')
    op.drop_column('users', 'last_failed_login')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
