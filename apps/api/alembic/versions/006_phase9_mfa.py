"""Phase 9: Add MFA support to users table

Revision ID: 006
Revises: 005
Create Date: 2025-01-15

Adds TOTP-based multi-factor authentication support:
- mfa_enabled: boolean flag
- mfa_secret: encrypted TOTP secret (base32)
- mfa_backup_codes: JSON array of hashed backup codes
- mfa_setup_at: timestamp of MFA setup completion
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add MFA columns to users table
    op.add_column('users', sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('mfa_secret', sa.String(length=32), nullable=True))
    op.add_column('users', sa.Column('mfa_backup_codes', postgresql.JSONB(), nullable=True))
    op.add_column('users', sa.Column('mfa_setup_at', sa.DateTime(timezone=True), nullable=True))
    
    # Index for querying users with MFA enabled
    op.create_index('ix_users_mfa_enabled', 'users', ['mfa_enabled'])


def downgrade() -> None:
    op.drop_index('ix_users_mfa_enabled', table_name='users')
    op.drop_column('users', 'mfa_setup_at')
    op.drop_column('users', 'mfa_backup_codes')
    op.drop_column('users', 'mfa_secret')
    op.drop_column('users', 'mfa_enabled')
