"""Persist procurement request idempotency and quote uniqueness."""

import sqlalchemy as sa

from alembic import op

revision = "ent_011"
down_revision = "ent_010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task_extensions", sa.Column("request_key_hash", sa.String(length=71), nullable=True))
    op.create_unique_constraint(
        "uq_task_extension_org_request_key",
        "task_extensions",
        ["organization_id", "request_key_hash"],
    )
    op.create_unique_constraint("uq_supplier_quote_task", "supplier_quotes", ["task_id"])


def downgrade() -> None:
    op.drop_constraint("uq_supplier_quote_task", "supplier_quotes", type_="unique")
    op.drop_constraint("uq_task_extension_org_request_key", "task_extensions", type_="unique")
    op.drop_column("task_extensions", "request_key_hash")
