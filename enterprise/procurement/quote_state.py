"""Quote lifecycle snapshots in the existing coordination table, never a second executor."""

import datetime
import json

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from enterprise.audit.models import AuditLogModel, generate_audit_log_id
from enterprise.procurement.models import (
    ProcurementCoordinationStateModel,
    ProcurementHumanReviewModel,
    SupplierQuoteModel,
)
from skyvern.forge.sdk.db.models import TaskModel

TEMPLATE_ID = "quote-task/v1"
STEPS = ("ready", "awaiting_approval", "running", "needs_human", "completed", "rejected", "terminated", "skipped")


async def load_quote_state(
    session: AsyncSession, task_id: str, org_id: str,
) -> ProcurementCoordinationStateModel | None:
    row = await session.scalar(select(ProcurementCoordinationStateModel).where(
        ProcurementCoordinationStateModel.task_id == task_id,
        ProcurementCoordinationStateModel.organization_id == org_id,
    ))
    if row is not None and row.current_plan.get("template_id") != TEMPLATE_ID:
        raise HTTPException(409, "Task has a different coordination owner")
    return row


def quote_state_response(row: ProcurementCoordinationStateModel | None) -> dict | None:
    if row is None:
        return None
    return {
        "task_id": row.task_id, "template_id": TEMPLATE_ID,
        "plan_id": row.current_plan["plan_id"], "current_step": row.current_plan["current_step"],
        "input_ref": row.task_id, "version": row.version,
        "skills": row.current_plan.get("skills", []),
        "skill_execution_mode": "real" if "skills" in row.current_plan else "not_connected",
    }


async def advance_quote_state(
    session: AsyncSession, *, task_id: str, org_id: str, department_id: str,
    executor: str, step: str, expected_version: int | None = None, native_extraction: bool = False,
) -> int:
    """Stage snapshot and safe audit in the caller's business transaction; never commit here."""
    if step not in STEPS:
        raise ValueError("Unknown quote step")
    row = await load_quote_state(session, task_id, org_id)
    version = row.version if row is not None else 0
    if expected_version is not None and expected_version != version:
        raise HTTPException(409, "Quote state version conflict")
    if row is not None and row.current_plan["current_step"] == step:
        current = await session.scalar(select(ProcurementCoordinationStateModel.version).where(
            ProcurementCoordinationStateModel.task_id == task_id,
            ProcurementCoordinationStateModel.organization_id == org_id,
            ProcurementCoordinationStateModel.version == version,
        ).with_for_update())
        if current is None:
            raise HTTPException(409, "Quote state version conflict")
        return version
    if row is not None:
        previous = row.current_plan["current_step"]
        allowed = {
            "awaiting_approval": {"ready", "rejected"},
            "ready": {"running", "completed", "needs_human"},
            "running": {"completed", "needs_human"},
            "needs_human": {"completed", "terminated", "skipped"},
        }
        if step not in allowed.get(previous, set()):
            raise HTTPException(409, "Quote state transition conflict")
    plan = dict(row.current_plan) if row is not None else {
        "plan_id": "quote:" + task_id, "template_id": TEMPLATE_ID,
        "navigation_goal": "Collect one evidence-backed supplier quote",
        "subtasks": [], "input_ref": task_id,
    }
    plan["current_step"] = step
    skill = {
        "step_id": "table_extract:0", "skill_name": "table_extract", "task_id": task_id,
        "status": {"ready": "pending", "awaiting_approval": "blocked"}.get(step, step),
        "artifact_id": None,
    }
    if step == "completed":
        native_status = await session.scalar(select(TaskModel.status).where(
            TaskModel.task_id == task_id, TaskModel.organization_id == org_id,
        ))
        if native_status != "completed" or not native_extraction:
            skill["status"] = "manual_completed"
        skill["artifact_id"] = await session.scalar(select(SupplierQuoteModel.artifact_id).where(
            SupplierQuoteModel.task_id == task_id, SupplierQuoteModel.organization_id == org_id,
        ))
    if step in ("needs_human", "terminated", "skipped"):
        skill["artifact_id"] = await session.scalar(select(ProcurementHumanReviewModel.artifact_id).where(
            ProcurementHumanReviewModel.task_id == task_id,
            ProcurementHumanReviewModel.organization_id == org_id,
        ))
    plan["skills"] = [skill]
    if step == "completed" and "orchestration" in plan:
        plan["orchestration"] = {
            **plan["orchestration"], "steps": [],
            "completed": (["execute_native"] if native_status == "completed" else []) + ["persist_quote"],
        }
    lifecycle = {
        "completed": "completed", "needs_human": "needs_human",
        "rejected": "failed", "terminated": "failed", "skipped": "failed",
    }.get(step, "running")
    values = dict(current_plan=plan, status=lifecycle, version=version + 1, modified_at=datetime.datetime.utcnow())
    if "orchestration" in plan:
        values["completed_subtask_ids"] = plan["orchestration"]["completed"]
    if row is None:
        session.add(ProcurementCoordinationStateModel(
            task_id=task_id, organization_id=org_id, navigation_goal=plan["navigation_goal"],
            completed_subtask_ids=[], max_replans=0, total_replans=0, **values,
        ))
    else:
        result = await session.execute(update(ProcurementCoordinationStateModel).where(
            ProcurementCoordinationStateModel.task_id == task_id,
            ProcurementCoordinationStateModel.organization_id == org_id,
            ProcurementCoordinationStateModel.version == version,
        ).values(**values))
        if result.rowcount != 1:
            raise HTTPException(409, "Quote state version conflict")
    session.add(AuditLogModel(
        audit_log_id=generate_audit_log_id(), task_id=task_id, organization_id=org_id,
        department_id=department_id, executor=executor, action_index=version + 1,
        action_type="quote_state_changed", business_object_type="quote_plan",
        business_object_id=plan["plan_id"], execution_result=step,
        input_value=json.dumps({"template_id": TEMPLATE_ID, "step": step, "version": version + 1}),
    ))
    session.add(AuditLogModel(
        audit_log_id=generate_audit_log_id(), task_id=task_id, organization_id=org_id,
        department_id=department_id, executor=executor, action_index=version + 1,
        action_type="skill_state_changed", business_object_type="quote_skill",
        business_object_id=plan["plan_id"] + ":" + skill["step_id"],
        execution_result=skill["status"], input_value=json.dumps(skill),
    ))
    return version + 1


async def save_quote_plan(
    session: AsyncSession, *, task_id: str, org_id: str, department_id: str,
    executor: str, plan: dict,
) -> None:
    """Save a bounded plan and its audit atomically, under the caller's execution claim."""
    row = await load_quote_state(session, task_id, org_id)
    if row is None:
        await advance_quote_state(
            session, task_id=task_id, org_id=org_id, department_id=department_id,
            executor=executor, step="ready",
        )
        await session.flush()
        row = await load_quote_state(session, task_id, org_id)
    if row.current_plan["current_step"] not in ("ready", "running"):
        raise HTTPException(409, "Quote state cannot be planned")
    version = row.version
    if row.current_plan.get("orchestration") == plan:
        current = await session.scalar(select(ProcurementCoordinationStateModel.version).where(
            ProcurementCoordinationStateModel.task_id == task_id,
            ProcurementCoordinationStateModel.organization_id == org_id,
            ProcurementCoordinationStateModel.version == version,
        ).with_for_update())
        if current is None:
            raise HTTPException(409, "Quote state version conflict")
        return
    replanned = row.current_plan.get("orchestration") is not None
    result = await session.execute(update(ProcurementCoordinationStateModel).where(
        ProcurementCoordinationStateModel.task_id == task_id,
        ProcurementCoordinationStateModel.organization_id == org_id,
        ProcurementCoordinationStateModel.version == version,
    ).values(
        current_plan={**row.current_plan, "orchestration": plan}, version=version + 1,
        completed_subtask_ids=plan["completed"], modified_at=datetime.datetime.utcnow(),
        max_replans=1, total_replans=row.total_replans + int(replanned),
    ))
    if result.rowcount != 1:
        raise HTTPException(409, "Quote state version conflict")
    session.add(AuditLogModel(
        audit_log_id=generate_audit_log_id(), task_id=task_id, organization_id=org_id,
        department_id=department_id, executor=executor, action_index=version + 1,
        action_type="quote_plan_updated", business_object_type="quote_plan",
        business_object_id=row.current_plan["plan_id"], execution_result=plan["source"],
        input_value=json.dumps(plan),
    ))
