"""Versioned server policy; database facts resolve the approval recipient scope."""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

from enterprise.auth.models import DepartmentModel, EnterpriseUserModel, UserDepartmentRoleModel
from enterprise.procurement.models import ProcurementCategoryModel, UserProcurementCategoryModel

from .risk_keywords import CRITICAL_AMOUNT_CNY, HIGH_AMOUNT_CNY, MEDIUM_AMOUNT_CNY
from .routing import ApprovalRoute, route_approval

POLICY_VERSION = "approval-cny-v1"
POLICY_EFFECTIVE_AT = datetime(2026, 9, 22, tzinfo=timezone.utc)


def policy_snapshot(amount: Decimal) -> dict:
    threshold = next((value for value in (CRITICAL_AMOUNT_CNY, HIGH_AMOUNT_CNY, MEDIUM_AMOUNT_CNY)
                      if amount >= value), None)
    return dict(total_amount_cny=amount, currency="CNY", matched_threshold_cny=threshold,
                policy_version=POLICY_VERSION, policy_effective_at=POLICY_EFFECTIVE_AT)


async def resolve_approval_route(session, *, org_id: str, department_id: str, category_id: str,
                                 requester_user_id: str, risk_level: str) -> ApprovalRoute:
    compliance_id = None
    if risk_level == "critical":
        departments = (await session.scalars(select(DepartmentModel.department_id).where(
            DepartmentModel.organization_id == org_id,
            DepartmentModel.department_code == "COMPLIANCE",
            DepartmentModel.deleted_at.is_(None),
        ))).all()
        if len(departments) != 1:
            raise HTTPException(422, "Exactly one same-organization compliance department is required")
        compliance_id = departments[0]
    route = route_approval(risk_level, department_id, category_id, compliance_department_id=compliance_id)
    if route.requires_approval:
        approver = await session.scalar(
            select(EnterpriseUserModel.user_id)
            .join(UserDepartmentRoleModel, UserDepartmentRoleModel.user_id == EnterpriseUserModel.user_id)
            .join(DepartmentModel, DepartmentModel.department_id == UserDepartmentRoleModel.department_id)
            .join(UserProcurementCategoryModel, UserProcurementCategoryModel.user_id == EnterpriseUserModel.user_id)
            .join(ProcurementCategoryModel,
                  ProcurementCategoryModel.category_id == UserProcurementCategoryModel.category_id)
            .where(
                EnterpriseUserModel.organization_id == org_id,
                EnterpriseUserModel.user_id != requester_user_id,
                EnterpriseUserModel.is_active.is_(True),
                EnterpriseUserModel.deleted_at.is_(None),
                DepartmentModel.organization_id == org_id,
                DepartmentModel.deleted_at.is_(None),
                DepartmentModel.department_id == route.approver_department_id,
                UserDepartmentRoleModel.role == route.approver_role,
                ProcurementCategoryModel.organization_id == org_id,
                ProcurementCategoryModel.category_id == category_id,
            ).limit(1)
        )
        if approver is None:
            raise HTTPException(422, "No eligible independent department/category approver is configured")
    return route
