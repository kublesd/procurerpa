"""Guards and transactional evidence around the existing native Workflow engine."""

import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select

from enterprise.agent.quote_planner import plan_steps
from enterprise.audit.models import ActionType, AuditLogModel
from enterprise.auth.dependencies import _load_current_user
from enterprise.auth.models import TaskExtensionModel
from enterprise.procurement.routes import _assert_procurement_operator
from enterprise.skills.executor import SkillStep, compile_skill_pipeline
from enterprise.workflows.models import WorkflowInstanceModel as Instance
from skyvern.forge import app
from skyvern.forge.sdk.db.models import ArtifactModel, CredentialModel, TaskModel, WorkflowRunBlockModel

MARKER = "enterprise-skill/v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def is_enterprise(workflow):
    return getattr(workflow, "description", None) == MARKER


def response(row):
    return dict(
        instance_id=row.instance_id,
        template_id=row.template_id,
        workflow_run_id=row.workflow_run_id,
        status=row.status,
        version=row.version,
        steps=row.state["steps"],
        plan=row.state.get("plan"),
        execution_mode="real",
        data_mode="controlled_demo",
    )


def audit(session, row, event):
    session.add(
        AuditLogModel(
            task_id=row.workflow_run_id or row.instance_id,
            organization_id=row.organization_id,
            department_id=row.department_id,
            executor=row.state.get("runtime_user_id", row.created_by),
            action_index=row.version,
            action_type=ActionType.CUSTOM.value,
            business_object_type="native_workflow",
            business_object_id=row.instance_id,
            target_element=json.dumps(
                {
                    "event": event,
                    "template_id": row.template_id,
                    "version": row.version,
                    "status": row.status,
                    "steps": row.state["steps"],
                },
                sort_keys=True,
            ),
            execution_result="success" if row.status == "completed" else row.status,
        )
    )


async def credential_metadata(session, org_id, credential_id, url, revision=None):
    # Select metadata only: never read username, password, TOTP, or vault item contents here.
    credential = (
        await session.execute(
            select(
                CredentialModel.modified_at,
                CredentialModel.vault_type,
                CredentialModel.credential_type,
                CredentialModel.tested_url,
                CredentialModel.browser_profile_id,
                CredentialModel.totp_type,
            ).where(
                CredentialModel.credential_id == credential_id,
                CredentialModel.organization_id == org_id,
                CredentialModel.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if (
        credential is None
        or credential.credential_type != "password"
        or credential.tested_url != url
        or credential.browser_profile_id
        or credential.totp_type not in (None, "none")
    ):
        raise HTTPException(409, "Workflow credential unavailable for this purpose")
    if (credential.vault_type or "bitwarden") not in app.CREDENTIAL_VAULT_SERVICES:
        raise HTTPException(409, "Workflow credential provider not_connected")
    current = credential.modified_at.isoformat()
    if revision is not None and revision != current:
        raise HTTPException(409, "Workflow credential version changed")
    return current


async def authorized_actor(row):
    user = await _load_current_user(row.state.get("runtime_user_id", row.created_by))
    if user is None or user.org_id != row.organization_id:
        raise HTTPException(403, "Workflow requester unavailable")
    _assert_procurement_operator(user, row.organization_id, row.department_id, row.category_id)


async def load_native_instance(session, workflow, run_id, org_id, lock=False):
    query = select(Instance).where(Instance.workflow_run_id == run_id, Instance.organization_id == org_id)
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None or row.workflow_id != workflow.workflow_id:
        raise HTTPException(409, "Native Workflow binding unavailable")
    if digest(workflow.workflow_definition.model_dump(mode="json")) != row.state["workflow_digest"]:
        raise HTTPException(409, "Native Workflow definition changed")
    return row


async def check_credential_binding(workflow, run_id, org_id, credential_id):
    if not is_enterprise(workflow):
        return
    async with app.DATABASE.Session() as session:
        row = await load_native_instance(session, workflow, run_id, org_id)
        if row.status != "running" or credential_id != row.state["credential_id"]:
            raise HTTPException(409, "Native Workflow credential binding unavailable")
        await authorized_actor(row)
        await credential_metadata(session, org_id, credential_id, row.state["url"], row.state["credential_revision"])


async def before_native_block(workflow, run_id, org_id, label):
    if not is_enterprise(workflow):
        return
    async with app.DATABASE.Session() as session:
        row = await load_native_instance(session, workflow, run_id, org_id, lock=True)
        await authorized_actor(row)
        await credential_metadata(
            session, org_id, row.state["credential_id"], row.state["url"], row.state["credential_revision"]
        )
        steps = [dict(step) for step in row.state["steps"]]
        pending = next((step for step in steps if step["status"] != "completed"), None)
        if row.state["plan"]["steps"] != [step["label"] for step in steps if step["status"] != "completed"]:
            raise HTTPException(409, "Native plan order rejected")
        if row.status != "running" or pending is None or pending["label"] != label or pending["status"] != "pending":
            raise HTTPException(409, "Native step replay or order rejected")
        pending["status"] = "running"
        row.state = {**row.state, "steps": steps}
        row.version += 1
        audit(session, row, "skill_started")
        await session.commit()


async def after_native_block(workflow, run_id, org_id, label, result):
    if not is_enterprise(workflow):
        return
    async with app.DATABASE.Session() as session:
        row = await load_native_instance(session, workflow, run_id, org_id, lock=True)
        steps = [dict(step) for step in row.state["steps"]]
        step = next(item for item in steps if item["label"] == label)
        if row.status != "running" or step["status"] != "running":
            raise HTTPException(409, "Native step state changed")
        native = await session.scalar(
            select(WorkflowRunBlockModel).where(
                WorkflowRunBlockModel.workflow_run_block_id == result.workflow_run_block_id,
                WorkflowRunBlockModel.workflow_run_id == run_id,
                WorkflowRunBlockModel.organization_id == org_id,
                WorkflowRunBlockModel.label == label,
            )
        )
        task = (
            None
            if native is None
            else await session.scalar(
                select(TaskModel).where(
                    TaskModel.task_id == native.task_id,
                    TaskModel.workflow_run_id == run_id,
                    TaskModel.organization_id == org_id,
                )
            )
        )
        artifacts = (
            []
            if task is None
            else list(
                (
                    await session.scalars(
                        select(ArtifactModel.artifact_id).where(
                            ArtifactModel.task_id == task.task_id, ArtifactModel.organization_id == org_id
                        )
                    )
                ).all()
            )
        )
        complete = bool(
            native
            and task
            and artifacts
            and task.status == "completed"
            and native.status == "completed"
            and result.status == "completed"
        )
        if complete and label.startswith("table_extract_"):
            headers = row.state.get("headers", {}).get(label, [])
            try:
                compile_skill_pipeline(
                    [SkillStep("table_extract", {"headers": headers})]
                ).validate_extracted_information(task.extracted_information)
            except ValueError:
                complete = False
        if complete and label.startswith("file_download_"):
            complete = bool(
                isinstance(result.output_parameter_value, dict)
                and result.output_parameter_value.get("downloaded_files")
            )
        if task is not None and not await session.scalar(
            select(TaskExtensionModel.task_id).where(TaskExtensionModel.task_id == task.task_id)
        ):
            session.add(
                TaskExtensionModel(
                    task_id=task.task_id,
                    organization_id=org_id,
                    department_id=row.department_id,
                    category_id=row.category_id,
                    created_by=row.created_by,
                    risk_level="medium",
                )
            )
        step.update(
            status="completed" if complete else "needs_human",
            task_id=task.task_id if task else None,
            artifact_ids=artifacts,
        )
        completed = [item["label"] for item in steps if item["status"] == "completed"]
        previous = row.state.get("plan")
        plan = (
            await plan_steps(tuple(item["label"] for item in steps), completed=completed, previous=previous)
            if complete
            else previous
        )
        row.state = {**row.state, "steps": steps, "plan": plan}
        row.status = (
            "completed"
            if all(item["status"] == "completed" for item in steps)
            else "running"
            if complete
            else "needs_human"
        )
        row.version += 1
        audit(session, row, "skill_completed" if complete else "skill_needs_human")
        await session.commit()
        if not complete:
            raise HTTPException(409, "Native Skill evidence unavailable; human review required")


async def fail_native(workflow, run_id, org_id):
    if not is_enterprise(workflow):
        return
    async with app.DATABASE.Session() as session:
        row = await session.scalar(
            select(Instance)
            .where(Instance.workflow_run_id == run_id, Instance.organization_id == org_id)
            .with_for_update()
        )
        if row is not None and row.status not in ("completed", "terminated", "needs_human"):
            row.status = "needs_human"
            row.version += 1
            audit(session, row, "native_failure")
            await session.commit()


def current_native_context():
    from skyvern.forge.sdk.core import skyvern_context

    native = skyvern_context.current()
    if native is None or not native.workflow_run_id:
        return None
    manager = app.WORKFLOW_CONTEXT_MANAGER
    context = manager.workflow_run_contexts.get(native.workflow_run_id) if manager else None
    return context if context and is_enterprise(context.workflow) else None


def safe_model_inputs(prompt, screenshots, use_message_history):
    context = current_native_context()
    if context is None:
        return prompt, screenshots
    if use_message_history:
        raise ValueError("Enterprise Workflow message history is disabled")
    # Text-only controlled portals avoid sending credential-bearing pixels to a model.
    return context.mask_secrets_in_data(prompt), None


def safe_artifact_data(artifact_type, data, path):
    context = current_native_context()
    if context is None:
        return True, data, path
    kind = str(getattr(artifact_type, "value", artifact_type))
    if kind.startswith("screenshot") or kind in ("recording", "trace", "har", "pdf"):
        return False, None, None
    if path is not None:
        # Path-backed logs/binaries cannot be proven credential-free at this boundary.
        return False, None, None
    try:
        text = data.decode("utf-8")
    except (AttributeError, UnicodeDecodeError):
        return False, None, None
    return True, context.mask_secrets_in_data(text).encode("utf-8"), None


async def check_secret_input(context, page_url, *, frame_url=None):
    if not is_enterprise(context.workflow):
        return
    async with app.DATABASE.Session() as session:
        row = await load_native_instance(session, context.workflow, context.workflow_run_id, context.organization_id)
        if row.status != "running" or page_url != row.state["url"] or frame_url != row.state["url"]:
            raise HTTPException(409, "Credential input outside the controlled portal rejected")
        await authorized_actor(row)
        await credential_metadata(
            session, row.organization_id, row.state["credential_id"], row.state["url"], row.state["credential_revision"]
        )
