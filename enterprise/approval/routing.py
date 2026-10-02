"""Risk-to-approval routing mapper.

Maps risk levels to approval requirements:
- low: no action
- medium: log only, no approval needed
- high: route to department approver
- critical: route to a server-resolved compliance department approver
"""

from dataclasses import dataclass, field


@dataclass
class ApprovalRoute:
    """Describes who needs to approve and who should be notified."""

    requires_approval: bool
    approver_department_id: str | None = None
    approver_role: str = "approver"
    notify_department_ids: list[str] = field(default_factory=list)
    notify_roles: list[str] = field(default_factory=list)
    description: str = ""
    approver_category_id: str | None = None


# Legacy demo identifiers; production resolves COMPLIANCE within its organization.
COMPLIANCE_DEPT_ID = "dept_compliance"
RISK_MGMT_DEPT_ID = "dept_risk_mgmt"


def route_approval(
    risk_level: str,
    source_department_id: str,
    category_id: str | None = None,
    *,
    procurement_category_id: str | None = None,
    compliance_department_id: str | None = None,
) -> ApprovalRoute:
    """Determine the approval route based on risk level.

    Args:
        risk_level: The assessed risk level ("low", "medium", "high", "critical").
        source_department_id: The department that initiated the operation.

    Returns:
        ApprovalRoute describing the required approval flow.
    """
    category_id = category_id or procurement_category_id

    if risk_level == "low":
        return ApprovalRoute(
            requires_approval=False,
            description="Low risk — no approval required",
        )

    if risk_level == "medium":
        return ApprovalRoute(
            requires_approval=False,
            description="Medium risk — logged for audit, no approval required",
        )

    if risk_level == "high":
        return ApprovalRoute(
            requires_approval=True,
            approver_department_id=source_department_id,
            approver_category_id=category_id,
            approver_role="approver",
            description=(
                f"High risk — requires approver in department {source_department_id}"
                + (f" for procurement category {category_id}" if category_id else "")
            ),
        )

    if risk_level == "critical":
        if not compliance_department_id:
            raise ValueError("Critical approval requires a resolved compliance department")
        return ApprovalRoute(
            requires_approval=True,
            approver_department_id=compliance_department_id,
            approver_category_id=category_id,
            approver_role="approver",
            description="Critical risk — requires same-organization compliance approver",
        )

    # Unknown risk level — treat as high conservatively
    return ApprovalRoute(
        requires_approval=True,
        approver_department_id=source_department_id,
        approver_category_id=category_id,
        approver_role="approver",
        description=f"Unknown risk level '{risk_level}' — treated as high risk",
    )
