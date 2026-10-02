"""Persist enterprise native Workflow authorization and redacted step evidence."""

import sqlalchemy as sa

from alembic import op

revision = "ent_013"
down_revision = "ent_012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "procurement_workflow_instances",
        sa.Column("instance_id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("organizations.organization_id"), nullable=False),
        sa.Column("department_id", sa.String(), sa.ForeignKey("departments.department_id"), nullable=False),
        sa.Column("category_id", sa.String(), sa.ForeignKey("procurement_categories.category_id"), nullable=False),
        sa.Column("created_by", sa.String(), sa.ForeignKey("enterprise_users.user_id"), nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        sa.Column("idempotency_hash", sa.String(), nullable=False),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("workflow_id", sa.String()),
        sa.Column("workflow_run_id", sa.String(), unique=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_hash", name="uq_workflow_instance_idempotency"),
        sa.CheckConstraint("version >= 1", name="ck_workflow_instance_version"),
        sa.CheckConstraint(
            "status IN ('preparing','ready','running','completed','failed','needs_human','terminated')",
            name="ck_workflow_instance_status",
        ),
    )
    op.create_index(
        "ix_procurement_workflow_instances_organization_id", "procurement_workflow_instances", ["organization_id"]
    )


def downgrade():
    op.drop_table("procurement_workflow_instances")
