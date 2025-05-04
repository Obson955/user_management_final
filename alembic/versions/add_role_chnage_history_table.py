"""add role change history table

Revision ID: add_role_change_history_table
Revises: 25d814bc83ed
Create Date: 2025-05-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_role_change_history_table'
down_revision = '25d814bc83ed'
branch_labels = None
depends_on = None


def upgrade():
    # Create role_change_history table
    op.create_table('role_change_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('changed_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('previous_role', sa.String(50), nullable=False),
        sa.Column('new_role', sa.String(50), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('reason', sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on user_id for faster lookups
    op.create_index(op.f('ix_role_change_history_user_id'), 'role_change_history', ['user_id'], unique=False)
    
    # Create index on changed_at for faster sorting and filtering
    op.create_index(op.f('ix_role_change_history_changed_at'), 'role_change_history', ['changed_at'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_role_change_history_changed_at'), table_name='role_change_history')
    op.drop_index(op.f('ix_role_change_history_user_id'), table_name='role_change_history')
    
    # Drop table
    op.drop_table('role_change_history')
