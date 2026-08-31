"""create ai_instructions table

Revision ID: c9d0e1f2a3b4
Revises: c8d9e0f1a2b3
Create Date: 2026-08-31 14:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_instructions",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("data_source_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_instructions_data_source_id", "ai_instructions", ["data_source_id"], unique=False)
    op.create_index("ix_ai_instructions_org_id", "ai_instructions", ["org_id"], unique=False)


def downgrade():
    op.drop_index("ix_ai_instructions_org_id", table_name="ai_instructions")
    op.drop_index("ix_ai_instructions_data_source_id", table_name="ai_instructions")
    op.drop_table("ai_instructions")
