"""commits replace pull requests

Revision ID: d4a7e9b1c2f3
Revises: 9e642aab369f
Create Date: 2026-11-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a7e9b1c2f3'
down_revision: Union[str, Sequence[str], None] = '9e642aab369f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index('ix_pull_requests_repo_number', table_name='pull_requests')
    op.drop_table('pull_requests')
    op.create_table('commits',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workspace_id', sa.Integer(), nullable=False),
    sa.Column('repo', sa.Text(), nullable=False),
    sa.Column('sha', sa.Text(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('author', sa.Text(), nullable=False),
    sa.Column('branch', sa.Text(), nullable=False),
    sa.Column('committed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_commits_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_commits')),
    sa.UniqueConstraint('workspace_id', 'repo', 'sha', name=op.f('uq_commits_workspace_id'))
    )
    op.create_table('commit_issues',
    sa.Column('commit_id', sa.Integer(), nullable=False),
    sa.Column('issue_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['commit_id'], ['commits.id'], name=op.f('fk_commit_issues_commit_id_commits'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], name=op.f('fk_commit_issues_issue_id_issues'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('commit_id', 'issue_id', name=op.f('pk_commit_issues'))
    )
    op.create_index(op.f('ix_commit_issues_issue_id'), 'commit_issues', ['issue_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_commit_issues_issue_id'), table_name='commit_issues')
    op.drop_table('commit_issues')
    op.drop_table('commits')
    op.create_table('pull_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('issue_id', sa.Integer(), nullable=False),
    sa.Column('repo', sa.Text(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('state', sa.Text(), nullable=False),
    sa.Column('branch', sa.Text(), nullable=False),
    sa.Column('author', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("state IN ('open', 'draft', 'merged', 'closed')", name=op.f('ck_pull_requests_state_valid')),
    sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], name=op.f('fk_pull_requests_issue_id_issues'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pull_requests')),
    sa.UniqueConstraint('issue_id', 'repo', 'number', name=op.f('uq_pull_requests_issue_id'))
    )
    op.create_index('ix_pull_requests_repo_number', 'pull_requests', ['repo', 'number'], unique=False)
