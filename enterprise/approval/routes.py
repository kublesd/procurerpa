"""Database-backed single-level procurement approval routes."""

import datetime
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select

from enterprise.audit.logger import record_audit_event, write_audit_log
from enterprise.audit.models import ActionType
from enterprise.auth.dependencies import get_current_user, require_any_operator, require_approver
from enterprise.auth.models import TaskExtensionModel
from enterprise.auth.schemas import UserContext
from skyvern.forge import app as forge_app
from skyvern.forge.sdk.executor.factory import AsyncExecutorFactory
from skyvern.forge.sdk.schemas.tasks import TaskStatus

from .models import ApprovalRequestModel, ApprovalStatus
from .notifications import publish_update, wait_for_update

router = APIRouter(prefix="/enterprise/approvals", tags=["approvals"])


class ApprovalResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approval_id: str
    task_id: str
    organization_id: str
    department_id: str
    business_line_id: str | None
    requester_user_id: str
    risk_level: str
    risk_reason: str
    operation_description: str | None
    screenshot_path: str | None
    approver_department_id: str
    status: str
    requested_at: datetime.datetime
    timeout_seconds: int
    category_id: str | None = None
    total_amount_cny: Decimal | None = None
    currency: str | None = None
    matched_threshold_cny: Decimal | None = None
    policy_version: str | None = None
    policy_effective_at: datetime.datetime | None = None


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(default="", max_length=2000)


class DecisionResponse(BaseModel):
    approval_id: str
    status: str
    decided_at: datetime.datetime
    message: str


class ContinueResponse(BaseModel):
    approval_id: str
    task_id: str
    task_status: str


def _user_can_approve(
    user: UserContext,
    approval: ApprovalRequestModel,
    category_id: str | None = None,
) -> bool:
    category_id = getattr(approval, "category_id", None) or category_id
    if approval.organization_id != user.org_id or approval.requester_user_id == user.user_id:
        return False
    if getattr(approval, "policy_version", None):
        return (
            category_id is not None and user.has_procurement_category(category_id)
            and user.get_role_in_department(approval.approver_department_id) == approval.approver_role
        )
    if user.is_org_admin or user.has_cross_org_approve:
        return True
    if category_id is not None and not user.has_procurement_category(category_id):
        return False
    return user.get_role_in_department(approval.approver_department_id) == "approver"


async def _locked_approval(session, approval_id: str) -> ApprovalRequestModel:
    approval = await session.scalar(
        select(ApprovalRequestModel)
        .where(ApprovalRequestModel.approval_id == approval_id)
        .with_for_update()
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    return approval


@router.get("/pending", response_model=list[ApprovalResponseSchema])
async def list_pending_approvals(user: UserContext = Depends(require_approver)):
    statement = select(ApprovalRequestModel).where(
        ApprovalRequestModel.organization_id == user.org_id,
        ApprovalRequestModel.status == ApprovalStatus.PENDING.value,
        ApprovalRequestModel.requester_user_id != user.user_id,
    )
    departments = [
        role.department_id for role in user.department_roles if role.role == "approver"
    ]
    legacy_category = (
        select(TaskExtensionModel.task_id)
        .where(
            TaskExtensionModel.task_id == ApprovalRequestModel.task_id,
            TaskExtensionModel.organization_id == user.org_id,
            TaskExtensionModel.category_id.in_(user.procurement_category_ids),
        )
        .exists()
    )
    scoped = and_(
        ApprovalRequestModel.approver_department_id.in_(departments),
        or_(ApprovalRequestModel.category_id.in_(user.procurement_category_ids),
            and_(ApprovalRequestModel.category_id.is_(None), legacy_category)),
    )
    if user.is_org_admin or user.has_cross_org_approve:
        statement = statement.where(or_(ApprovalRequestModel.policy_version.is_(None), scoped))
    else:
        statement = statement.where(scoped)
    async with forge_app.DATABASE.Session() as session:
        return (await session.scalars(statement.order_by(ApprovalRequestModel.requested_at))).all()


async def _decide(
    approval_id: str,
    decision: ApprovalStatus,
    note: str,
    user: UserContext,
) -> DecisionResponse:
    from enterprise.procurement.quote_state import advance_quote_state
    from enterprise.procurement.routes import _QUOTE_EXTRACTION_GOAL
    from skyvern.forge.sdk.db.models import TaskModel

    async with forge_app.DATABASE.Session() as session:
        approval = await _locked_approval(session, approval_id)
        if approval.organization_id != user.org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-organization approval is forbidden")
        if approval.requester_user_id == user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requesters cannot approve their own task")
        # Legacy approvals have no snapshot; retain their TaskExtension category scope.
        category_id = getattr(approval, "category_id", None) or await session.scalar(
            select(TaskExtensionModel.category_id).where(
                TaskExtensionModel.task_id == approval.task_id,
                TaskExtensionModel.organization_id == approval.organization_id,
            )
        )
        if not _user_can_approve(user, approval, category_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Approval is outside the user's department or procurement category",
            )
        if approval.status != ApprovalStatus.PENDING.value:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Approval is already {approval.status}")

        task = await session.scalar(select(TaskModel).where(
            TaskModel.task_id == approval.task_id, TaskModel.organization_id == approval.organization_id,
        ).with_for_update())
        if task is None or task.status != TaskStatus.created:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Procurement task is no longer awaiting approval")

        now = datetime.datetime.utcnow()
        approval.status = decision.value
        approval.approver_user_id = user.user_id
        approval.decided_at = now
        approval.decision_note = note
        audit_context = {
            "task_id": approval.task_id,
            "org_id": approval.organization_id,
            "department_id": approval.department_id,
            "business_line_id": approval.business_line_id,
        }
        if decision is ApprovalStatus.REJECTED:
            task.status = TaskStatus.canceled
        if getattr(task, "data_extraction_goal", None) == _QUOTE_EXTRACTION_GOAL:
            await advance_quote_state(
                session, task_id=approval.task_id, org_id=approval.organization_id,
                department_id=approval.department_id, executor=user.user_id,
                step="ready" if decision is ApprovalStatus.APPROVED else "rejected",
            )
        await write_audit_log(session, commit=False,
            **audit_context,
            business_object_type="approval",
            business_object_id=approval_id,
            action_index=4,
            action_type=(
                ActionType.APPROVAL_APPROVED.value
                if decision is ApprovalStatus.APPROVED
                else ActionType.APPROVAL_REJECTED.value
            ),
            executor=user.user_id,
            input_value={"decision_note": note},
            execution_result=decision.value,
            has_approval=True,
            approval_id=approval_id,
            approver_user_id=user.user_id,
        )
        await session.commit()
    await publish_update(user.org_id, approval_id, decision.value, user.user_id)
    return DecisionResponse(
        approval_id=approval_id,
        status=decision.value,
        decided_at=now,
        message="Approval granted" if decision is ApprovalStatus.APPROVED else "Approval rejected",
    )


async def _visible_approval(approval_id: str, user: UserContext) -> ApprovalResponseSchema:
    async with forge_app.DATABASE.Session() as session:
        approval = await session.scalar(select(ApprovalRequestModel).where(
            ApprovalRequestModel.approval_id == approval_id,
            ApprovalRequestModel.organization_id == user.org_id,
        ))
        if approval is None or approval.organization_id != user.org_id:
            raise HTTPException(404, "Approval request not found")
        category_id = approval.category_id or await session.scalar(select(TaskExtensionModel.category_id).where(
            TaskExtensionModel.task_id == approval.task_id,
            TaskExtensionModel.organization_id == user.org_id,
        ))
        if approval.requester_user_id != user.user_id and not _user_can_approve(user, approval, category_id):
            raise HTTPException(403, "Approval is outside the user's scope")
        return ApprovalResponseSchema.model_validate(approval)


@router.get("/{approval_id}", response_model=ApprovalResponseSchema)
async def get_approval(approval_id: str, user: UserContext = Depends(get_current_user)):
    return await _visible_approval(approval_id, user)


@router.get("/{approval_id}/updates", response_model=ApprovalResponseSchema)
async def approval_updates(
    approval_id: str,
    timeout: int = Query(default=20, ge=1, le=25),
    user: UserContext = Depends(get_current_user),
):
    current = await _visible_approval(approval_id, user)
    if current.status == ApprovalStatus.PENDING.value:
        await wait_for_update(user.org_id, approval_id, timeout)
        # A fresh session observes commits even if the event was lost or fabricated.
        from enterprise.auth.dependencies import _load_current_user

        refreshed_user = await _load_current_user(user.user_id)
        if refreshed_user is None:
            raise HTTPException(401, "User is inactive or no longer exists")
        return await _visible_approval(approval_id, refreshed_user)
    return current


@router.post("/{approval_id}/approve", response_model=DecisionResponse)
async def approve_request(
    approval_id: str,
    body: DecisionRequest = DecisionRequest(),
    user: UserContext = Depends(require_approver),
):
    return await _decide(approval_id, ApprovalStatus.APPROVED, body.note, user)


@router.post("/{approval_id}/reject", response_model=DecisionResponse)
async def reject_request(
    approval_id: str,
    body: DecisionRequest = DecisionRequest(),
    user: UserContext = Depends(require_approver),
):
    return await _decide(approval_id, ApprovalStatus.REJECTED, body.note, user)


@router.post("/{approval_id}/continue", response_model=ContinueResponse)
async def continue_request(
    approval_id: str,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(require_any_operator),
):
    from enterprise.procurement.routes import quote_continuation_payload, recover_quote_task

    async with forge_app.DATABASE.Session() as session:
        approval = await _locked_approval(session, approval_id)
        if approval.organization_id != user.org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-organization continuation is forbidden")
        if approval.requester_user_id != user.user_id and not user.is_org_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the requester can continue this task")
        if approval.status != ApprovalStatus.APPROVED.value:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only approved tasks can continue")

        approval_data = {
            "approval_id": approval.approval_id,
            "task_id": approval.task_id,
            "organization_id": approval.organization_id,
            "department_id": approval.department_id,
            "business_line_id": approval.business_line_id,
            "approver_user_id": approval.approver_user_id,
        }
        task = await forge_app.DATABASE.get_task(
            approval_data["task_id"], organization_id=approval_data["organization_id"],
        )
        if task is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Procurement task is unavailable")
        quote_payload = await quote_continuation_payload(task, user)
        if task.status != TaskStatus.created and quote_payload is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Procurement task has already continued")
        if quote_payload is None:
            # Claim the task while the approval row is locked so concurrent retries
            # cannot schedule the same native Task twice.
            await forge_app.DATABASE.update_task(
                approval_data["task_id"],
                status=TaskStatus.running,
                organization_id=approval_data["organization_id"],
            )
        browser_session_id = task.browser_session_id

    if quote_payload is not None:
        await recover_quote_task(approval_data["task_id"], user)
        task = await forge_app.DATABASE.get_task(
            approval_data["task_id"], organization_id=approval_data["organization_id"],
        )
        return ContinueResponse(
            approval_id=approval_data["approval_id"],
            task_id=approval_data["task_id"],
            task_status=task.status.value,
        )

    try:
        await AsyncExecutorFactory.get_executor().execute_task(
            request=None,
            background_tasks=background_tasks,
            task_id=approval_data["task_id"],
            organization_id=approval_data["organization_id"],
            max_steps_override=None,
            browser_session_id=browser_session_id,
            api_key=None,
        )
    except Exception as exc:
        try:
            await forge_app.DATABASE.update_task(
                approval_data["task_id"],
                status=TaskStatus.failed,
                organization_id=approval_data["organization_id"],
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Approved procurement task could not be started",
        ) from exc
    await record_audit_event(
        task_id=approval_data["task_id"],
        org_id=approval_data["organization_id"],
        department_id=approval_data["department_id"],
        business_line_id=approval_data["business_line_id"],
        business_object_type="approval",
        business_object_id=approval_data["approval_id"],
        action_index=5,
        action_type=ActionType.TASK_CONTINUED.value,
        executor=user.user_id,
        execution_result="running",
        has_approval=True,
        approval_id=approval_data["approval_id"],
        approver_user_id=approval_data["approver_user_id"],
    )
    return ContinueResponse(
        approval_id=approval_data["approval_id"],
        task_id=approval_data["task_id"],
        task_status=TaskStatus.running.value,
    )
