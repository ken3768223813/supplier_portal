"""SQE English Lab progress and material workflow

Revision ID: 8d4a2c9e710b
Revises: 5f7c4e2a91d0
Create Date: 2026-07-29 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "8d4a2c9e710b"
down_revision = "5f7c4e2a91d0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("drill_phrases", schema=None) as batch_op:
        batch_op.add_column(sa.Column("topic", sa.String(length=50), nullable=True))
        batch_op.add_column(
            sa.Column(
                "difficulty",
                sa.String(length=20),
                server_default="intermediate",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("context_cn", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("alternatives_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("chunks_json", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=20),
                server_default="approved",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("source_type", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("source_id", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )
        batch_op.create_index(batch_op.f("ix_drill_phrases_topic"), ["topic"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_drill_phrases_difficulty"), ["difficulty"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_drill_phrases_status"), ["status"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_drill_phrases_source_type"), ["source_type"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_drill_phrases_source_id"), ["source_id"], unique=False
        )

    op.execute("UPDATE drill_phrases SET topic = category WHERE topic IS NULL")
    op.execute(
        """
        UPDATE drill_phrases
        SET category = 'factory'
        WHERE category IN ('metallurgy', 'surface', 'electrical', 'measurement')
        """
    )

    op.create_table(
        "drill_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phrase_id", sa.Integer(), nullable=False),
        sa.Column("ease_factor", sa.Float(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("repetitions", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("successes", sa.Integer(), nullable=False),
        sa.Column("last_rating", sa.String(length=20), nullable=True),
        sa.Column("last_mode", sa.String(length=30), nullable=True),
        sa.Column("last_practiced_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["phrase_id"], ["drill_phrases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phrase_id"),
    )
    with op.batch_alter_table("drill_progress", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_drill_progress_phrase_id"), ["phrase_id"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_drill_progress_due_date"), ["due_date"], unique=False
        )

    op.create_table(
        "drill_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phrase_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=30), nullable=False),
        sa.Column("rating", sa.String(length=20), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["phrase_id"], ["drill_phrases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("drill_attempts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_drill_attempts_phrase_id"), ["phrase_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_drill_attempts_mode"), ["mode"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_drill_attempts_rating"), ["rating"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_drill_attempts_created_at"), ["created_at"], unique=False
        )


def downgrade():
    with op.batch_alter_table("drill_attempts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_drill_attempts_created_at"))
        batch_op.drop_index(batch_op.f("ix_drill_attempts_rating"))
        batch_op.drop_index(batch_op.f("ix_drill_attempts_mode"))
        batch_op.drop_index(batch_op.f("ix_drill_attempts_phrase_id"))
    op.drop_table("drill_attempts")

    with op.batch_alter_table("drill_progress", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_drill_progress_due_date"))
        batch_op.drop_index(batch_op.f("ix_drill_progress_phrase_id"))
    op.drop_table("drill_progress")

    op.execute(
        """
        UPDATE drill_phrases
        SET category = topic
        WHERE category = 'factory'
          AND topic IN ('metallurgy', 'surface', 'electrical', 'measurement')
        """
    )

    with op.batch_alter_table("drill_phrases", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_drill_phrases_source_id"))
        batch_op.drop_index(batch_op.f("ix_drill_phrases_source_type"))
        batch_op.drop_index(batch_op.f("ix_drill_phrases_status"))
        batch_op.drop_index(batch_op.f("ix_drill_phrases_difficulty"))
        batch_op.drop_index(batch_op.f("ix_drill_phrases_topic"))
        batch_op.drop_column("updated_at")
        batch_op.drop_column("source_id")
        batch_op.drop_column("source_type")
        batch_op.drop_column("status")
        batch_op.drop_column("chunks_json")
        batch_op.drop_column("alternatives_json")
        batch_op.drop_column("context_cn")
        batch_op.drop_column("difficulty")
        batch_op.drop_column("topic")
