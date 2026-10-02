"""Persist new approval policy snapshots without backfilling legacy decisions."""

import sqlalchemy as sa

from alembic import op

revision = "ent_012"
down_revision = "ent_011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("approval_requests", sa.Column("category_id", sa.String(), nullable=True))
    op.create_foreign_key("fk_approval_category", "approval_requests", "procurement_categories",
                          ["category_id"], ["category_id"])
    op.add_column("approval_requests", sa.Column("total_amount_cny", sa.Numeric(), nullable=True))
    op.add_column("approval_requests", sa.Column("currency", sa.String(3), nullable=True))
    op.add_column("approval_requests", sa.Column("matched_threshold_cny", sa.Numeric(), nullable=True))
    op.add_column("approval_requests", sa.Column("policy_version", sa.String(), nullable=True))
    op.add_column("approval_requests", sa.Column("policy_effective_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_constraint("fk_approval_category", "approval_requests", type_="foreignkey")
    for column in ("policy_effective_at", "policy_version", "matched_threshold_cny", "currency",
                   "total_amount_cny", "category_id"):
        op.drop_column("approval_requests", column)
