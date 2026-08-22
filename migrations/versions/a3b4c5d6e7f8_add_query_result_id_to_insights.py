"""add query_result_id to insights

Revision ID: a3b4c5d6e7f8
Revises: f1a2b3c4d5e6
Create Date: 2026-08-23 02:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a3b4c5d6e7f8"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("insights", sa.Column("query_result_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "insights_query_result_id_fkey",
        "insights",
        "query_results",
        ["query_result_id"],
        ["id"],
    )
    op.create_index(
        "ix_insights_definition_query_result",
        "insights",
        ["insight_definition_id", "query_result_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_insights_definition_query_result", table_name="insights")
    op.drop_constraint("insights_query_result_id_fkey", "insights", type_="foreignkey")
    op.drop_column("insights", "query_result_id")
