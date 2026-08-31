"""create ai_sql_pairs table

Revision ID: c8d9e0f1a2b3
Revises: c7d8e9f0a1b2
Create Date: 2026-08-31 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c8d9e0f1a2b3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_sql_pairs",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("data_source_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_sql_pairs_data_source_id", "ai_sql_pairs", ["data_source_id"], unique=False)
    op.create_index("ix_ai_sql_pairs_org_id", "ai_sql_pairs", ["org_id"], unique=False)


def downgrade():
    op.drop_index("ix_ai_sql_pairs_org_id", table_name="ai_sql_pairs")
    op.drop_index("ix_ai_sql_pairs_data_source_id", table_name="ai_sql_pairs")
    op.drop_table("ai_sql_pairs")
