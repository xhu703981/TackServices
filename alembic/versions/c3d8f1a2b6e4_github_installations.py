"""github installations: a workspace's GitHub App connection

Revision ID: c3d8f1a2b6e4
Revises: b7c1e2d4a9f0
Create Date: 2026-11-04 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d8f1a2b6e4'
down_revision: Union[str, Sequence[str], None] = 'b7c1e2d4a9f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('github_installations',
    sa.Column('workspace_id', sa.Integer(), nullable=False),
    sa.Column('installation_id', sa.BigInteger(), nullable=False),
    sa.Column('account_login', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_github_installations_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('workspace_id', name=op.f('pk_github_installations')),
    sa.UniqueConstraint('installation_id', name=op.f('uq_github_installations_installation_id'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('github_installations')
