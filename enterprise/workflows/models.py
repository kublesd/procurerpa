"""Enterprise authorization and safe evidence for one native Workflow run."""

import datetime
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from skyvern.forge.sdk.db.models import Base


class WorkflowInstanceModel(Base):
    __tablename__ = "procurement_workflow_instances"
    instance_id = Column(String, primary_key=True, default=lambda: "pwi_" + uuid4().hex)
    organization_id = Column(String, ForeignKey("organizations.organization_id"), nullable=False, index=True)
    department_id = Column(String, ForeignKey("departments.department_id"), nullable=False)
    category_id = Column(String, ForeignKey("procurement_categories.category_id"), nullable=False)
    created_by = Column(String, ForeignKey("enterprise_users.user_id"), nullable=False)
    template_id = Column(String, nullable=False)
    idempotency_hash = Column(String, nullable=False)
    request_hash = Column(String, nullable=False)
    workflow_id = Column(String, nullable=True)
    workflow_run_id = Column(String, nullable=True, unique=True)
    status = Column(String, nullable=False, default="preparing")
    version = Column(Integer, nullable=False, default=1)
    state = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    modified_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_hash", name="uq_workflow_instance_idempotency"),
        CheckConstraint("version >= 1", name="ck_workflow_instance_version"),
        CheckConstraint(
            "status IN ('preparing','ready','running','completed','failed','needs_human','terminated')",
            name="ck_workflow_instance_status",
        ),
    )
