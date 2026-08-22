"""create insight_definitions and link insights

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-08-23 02:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f1a2b3c4d5e6"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "insight_definitions",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("query_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["query_id"], ["queries.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insight_definitions_query_id", "insight_definitions", ["query_id"], unique=False)

    op.add_column("insights", sa.Column("insight_definition_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "insights_insight_definition_id_fkey",
        "insights",
        "insight_definitions",
        ["insight_definition_id"],
        ["id"],
    )
    op.create_index("ix_insights_insight_definition_id", "insights", ["insight_definition_id"], unique=False)

    # 既存グループへ list_insights を付与（既にある場合はスキップ）
    op.execute(
        """
        UPDATE groups
        SET permissions = array_append(permissions, 'list_insights')
        WHERE NOT ('list_insights' = ANY (permissions))
        """
    )


def downgrade():
    op.drop_index("ix_insights_insight_definition_id", table_name="insights")
    op.drop_constraint("insights_insight_definition_id_fkey", "insights", type_="foreignkey")
    op.drop_column("insights", "insight_definition_id")
    op.drop_index("ix_insight_definitions_query_id", table_name="insight_definitions")
    op.drop_table("insight_definitions")
