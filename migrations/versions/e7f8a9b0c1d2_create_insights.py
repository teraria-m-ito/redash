"""create insights table

Revision ID: e7f8a9b0c1d2
Revises: db0aca1ebd32
Create Date: 2026-08-23 01:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e7f8a9b0c1d2"
down_revision = "db0aca1ebd32"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "insights",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query_id", sa.Integer(), nullable=False),
        sa.Column("execute_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dimension_column_name", sa.String(length=255), nullable=False),
        sa.Column("category_column_name", sa.String(length=255), nullable=False),
        sa.Column("message_to", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["query_id"], ["queries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insights_query_id", "insights", ["query_id"], unique=False)
    op.create_index("ix_insights_execute_at", "insights", ["execute_at"], unique=False)


def downgrade():
    op.drop_index("ix_insights_execute_at", table_name="insights")
    op.drop_index("ix_insights_query_id", table_name="insights")
    op.drop_table("insights")
