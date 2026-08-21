"""structured control plan versions

Revision ID: 5f7c4e2a91d0
Revises: b2fc755aafb0
Create Date: 2026-07-29 10:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '5f7c4e2a91d0'
down_revision = 'b2fc755aafb0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('control_plans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('published_version_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('structure_status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('quality_score', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('source_template', sa.String(length=50), nullable=True))
        batch_op.create_index(batch_op.f('ix_control_plans_structure_status'), ['structure_status'], unique=False)

    op.create_table(
        'control_plan_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cp_id', sa.Integer(), nullable=False),
        sa.Column('version_no', sa.Integer(), nullable=False),
        sa.Column('revision', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('extract_status', sa.String(length=20), nullable=False),
        sa.Column('original_name', sa.String(length=255), nullable=False),
        sa.Column('stored_name', sa.String(length=255), nullable=False),
        sa.Column('rel_path', sa.String(length=500), nullable=False),
        sa.Column('mime', sa.String(length=100), nullable=True),
        sa.Column('size', sa.Integer(), nullable=True),
        sa.Column('file_sha256', sa.String(length=64), nullable=True),
        sa.Column('source_sheet', sa.String(length=255), nullable=True),
        sa.Column('source_template', sa.String(length=50), nullable=True),
        sa.Column('parser_version', sa.String(length=30), nullable=True),
        sa.Column('ai_model', sa.String(length=100), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('quality_score', sa.Integer(), nullable=True),
        sa.Column('quality_issues', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('structured_json', sa.Text(), nullable=True),
        sa.Column('extraction_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['cp_id'], ['control_plans.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cp_id', 'version_no', name='uq_cp_version_no'),
    )
    with op.batch_alter_table('control_plan_versions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_control_plan_versions_cp_id'), ['cp_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_control_plan_versions_extract_status'), ['extract_status'], unique=False)
        batch_op.create_index(batch_op.f('ix_control_plan_versions_file_sha256'), ['file_sha256'], unique=False)
        batch_op.create_index(batch_op.f('ix_control_plan_versions_status'), ['status'], unique=False)

    with op.batch_alter_table('process_steps', schema=None) as batch_op:
        batch_op.alter_column('process_name', existing_type=sa.String(length=100), type_=sa.String(length=255))
        batch_op.alter_column('machine', existing_type=sa.String(length=100), type_=sa.Text())
        batch_op.add_column(sa.Column('source_sheet', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('source_row', sa.Integer(), nullable=True))

    with op.batch_alter_table('control_characteristics', schema=None) as batch_op:
        batch_op.alter_column('char_name', existing_type=sa.String(length=150), type_=sa.String(length=255))
        batch_op.alter_column('spec_value', existing_type=sa.String(length=100), type_=sa.Text())
        batch_op.alter_column('control_method', existing_type=sa.String(length=150), type_=sa.Text())
        batch_op.add_column(sa.Column('char_type', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('char_code', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('special_class', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('measurement_method', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('inspector', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('source_sheet', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('source_row', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('confidence', sa.Float(), nullable=True))

    op.execute(
        """
        INSERT INTO control_plan_versions (
            cp_id, version_no, revision, status, extract_status,
            original_name, stored_name, rel_path, mime, size, created_at
        )
        SELECT
            id, 1, revision, 'review', 'pending',
            COALESCE(original_name, stored_name, 'legacy-file'),
            COALESCE(stored_name, original_name, 'legacy-file'),
            rel_path, mime, size, COALESCE(created_at, CURRENT_TIMESTAMP)
        FROM control_plans
        WHERE rel_path IS NOT NULL AND rel_path <> ''
        """
    )
    op.execute("UPDATE control_plans SET structure_status = 'pending' WHERE rel_path IS NOT NULL")


def downgrade():
    with op.batch_alter_table('control_characteristics', schema=None) as batch_op:
        batch_op.drop_column('confidence')
        batch_op.drop_column('source_row')
        batch_op.drop_column('source_sheet')
        batch_op.drop_column('inspector')
        batch_op.drop_column('measurement_method')
        batch_op.drop_column('special_class')
        batch_op.drop_column('char_code')
        batch_op.drop_column('char_type')
        batch_op.alter_column('control_method', existing_type=sa.Text(), type_=sa.String(length=150))
        batch_op.alter_column('spec_value', existing_type=sa.Text(), type_=sa.String(length=100))
        batch_op.alter_column('char_name', existing_type=sa.String(length=255), type_=sa.String(length=150))

    with op.batch_alter_table('process_steps', schema=None) as batch_op:
        batch_op.drop_column('source_row')
        batch_op.drop_column('source_sheet')
        batch_op.alter_column('machine', existing_type=sa.Text(), type_=sa.String(length=100))
        batch_op.alter_column('process_name', existing_type=sa.String(length=255), type_=sa.String(length=100))

    with op.batch_alter_table('control_plan_versions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_control_plan_versions_status'))
        batch_op.drop_index(batch_op.f('ix_control_plan_versions_file_sha256'))
        batch_op.drop_index(batch_op.f('ix_control_plan_versions_extract_status'))
        batch_op.drop_index(batch_op.f('ix_control_plan_versions_cp_id'))
    op.drop_table('control_plan_versions')

    with op.batch_alter_table('control_plans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_control_plans_structure_status'))
        batch_op.drop_column('source_template')
        batch_op.drop_column('quality_score')
        batch_op.drop_column('structure_status')
        batch_op.drop_column('published_version_id')
