"""google-only login: drop users.password_hash

Revision ID: b7c1e2d4a9f0
Revises: 5933f220251f
Create Date: 2026-11-04 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7c1e2d4a9f0'
down_revision: Union[str, Sequence[str], None] = '5933f220251f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The constraint reads password_hash, so it goes first. Users not linked to Google yet keep a NULL provider
    # and get linked by email on their first Google sign-in.
    op.drop_constraint(op.f('ck_users_can_log_in'), 'users', type_='check')
    op.drop_column('users', 'password_hash')


def downgrade() -> None:
    """Downgrade schema."""
    # Old passwords are gone for good; unlinked users come back with no way to log in, so the constraint
    # can only return as NOT VALID (enforced for new rows, existing ones not checked).
    op.add_column('users', sa.Column('password_hash', sa.Text(), nullable=True))
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_can_log_in "
        "CHECK (password_hash IS NOT NULL OR auth_provider IS NOT NULL) NOT VALID"
    )
