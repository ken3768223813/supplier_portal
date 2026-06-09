"""add is_pinned to trouble_reports

Revision ID: b2fc755aafb0
Revises: 258fff829a6f
Create Date: 2026-06-06 13:07:18.142230

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2fc755aafb0'
down_revision = '258fff829a6f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('trouble_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.create_index(batch_op.f('ix_trouble_reports_is_pinned'), ['is_pinned'], unique=False)


def downgrade():
    with op.batch_alter_table('trouble_reports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_trouble_reports_is_pinned'))
        batch_op.drop_column('is_pinned')

    # ### end Alembic commands ###
