"""Workflow template API routes.

Provides endpoints for:
- GET  /enterprise/workflows/templates         — list all templates
- GET  /enterprise/workflows/templates/{id}    — template detail
- POST /enterprise/workflows/instantiate/quote-task/v1 — native quote template
- POST /enterprise/workflows/instantiate/{id} — legacy templates fail closed
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from enterprise.auth.dependencies import CurrentUser, require_any_operator
from enterprise.auth.schemas import UserContext
from enterprise.procurement import routes as procurement_routes
from enterprise.tenant.context import tenant_context_for
from enterprise.tenant.query_filter import apply_tenant_filter
from skyvern.config import is_development_environment, settings
from skyvern.forge import app as forge_app
from skyvern.forge.sdk.db.models import TaskModel, WorkflowRunBlockModel, WorkflowRunModel
from skyvern.forge.sdk.executor.factory import AsyncExecutorFactory
from skyvern.forge.sdk.workflow.models.workflow import WorkflowRequestBody
from skyvern.services.workflow_service import prepare_workflow

from . import runtime
from .models import WorkflowInstanceModel as Instance
from .templates import (
    TEMPLATE_REGISTRY,
    build_skill_pipeline,
    compile_native_template,
    get_template,
    get_templates_by_industry,
)

router = APIRouter(prefix="/enterprise/workflows", tags=["workflows"])


# --- Pydantic response schemas ---


class ParamDefResponse(BaseModel):
    name: str
    label: str
    param_type: str
    required: bool
    sensitive: bool
    description: str
    default: str | None


class TemplateListItem(BaseModel):
    template_id: str
    name: str
    industry: str
    risk_level: str
    description: str
    tags: list[str]
    execution_mode: str = "real"
    data_mode: str = "controlled_demo"


class TemplateDetailResponse(BaseModel):
    template_id: str
    name: str
    industry: str
    risk_level: str
    description: str
    navigation_target: str
    expected_result: str
    approval_rule: str
    parameters: list[ParamDefResponse]
    tags: list[str]
    execution_mode: str = "real"
    data_mode: str = "controlled_demo"


class InstantiateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    department_id: str = Field(..., min_length=1, max_length=128)
    category_id: str = Field(..., min_length=1, max_length=128)
    parameters: dict[str, str] = Field(..., description="Parameter values")


# --- Routes ---


@router.get("/templates", response_model=list[TemplateListItem])
async def list_templates(
    user: CurrentUser,
    industry: str | None = None,
):
    """List all available workflow templates, optionally filtered by industry."""
    if industry:
        templates = get_templates_by_industry(industry)
    else:
        templates = list(TEMPLATE_REGISTRY.values())

    return [
        TemplateListItem(
            template_id=t.template_id,
            name=t.name,
            industry=t.industry.value,
            risk_level=t.risk_level,
            description=t.description,
            tags=t.tags,
        )
        for t in templates
    ]


@router.get("/templates/{template_id}", response_model=TemplateDetailResponse)
async def get_template_detail(
    template_id: str,
    user: CurrentUser,
):
    """Get detailed information about a specific workflow template."""
    template = get_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )

    return TemplateDetailResponse(
        template_id=template.template_id,
        name=template.name,
        industry=template.industry.value,
        risk_level=template.risk_level,
        description=template.description,
        navigation_target=template.navigation_target,
        expected_result=template.expected_result,
        approval_rule=template.approval_rule,
        parameters=[
            ParamDefResponse(
                name=p.name,
                label=p.label,
                param_type=p.param_type.value,
                required=p.required,
                sensitive=p.sensitive,
                description=p.description,
                default=p.default,
            )
            for p in template.parameters
        ],
        tags=template.tags,
    )


class NativeQuoteTemplateResponse(procurement_routes.QuoteTaskResponse):
    template_id: str = "quote-task/v1"
    execution_mode: str = "real"


@router.post("/instantiate/quote-task/v1", response_model=NativeQuoteTemplateResponse)
async def instantiate_quote_template(
    body: procurement_routes.QuoteTaskRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
    user: UserContext = Depends(require_any_operator),
) -> NativeQuoteTemplateResponse:
    """Run the credential-free quote template through the existing procurement boundary."""
    result = await procurement_routes.quote_task(
        payload=body,
        request=request,
        response=response,
        background_tasks=background_tasks,
        idempotency_key=idempotency_key,
        user=user,
    )
    return NativeQuoteTemplateResponse(**result.model_dump())


def _development_guard():
    if not is_development_environment(settings.ENV):
        raise HTTPException(404, "Controlled template execution unavailable")


async def _scoped_instance(session, instance_id, user, lock=False):
    query = apply_tenant_filter(
        select(Instance).where(Instance.instance_id == instance_id), Instance, tenant_context_for(user)
    )
    row = await session.scalar(query.with_for_update(skip_locked=True) if lock else query)
    if row is None:
        raise HTTPException(404 if not lock else 409, "Workflow instance unavailable")
    return row


def _requester(row, user):
    if row.created_by != user.user_id and not user.is_org_admin:
        raise HTTPException(403, "Only the requester or organization administrator may execute")
    procurement_routes._assert_procurement_operator(user, row.organization_id, row.department_id, row.category_id)


async def _dispatch(instance_id, user, request, background_tasks, expected_version):
    async with forge_app.DATABASE.Session() as session:
        row = await _scoped_instance(session, instance_id, user, lock=True)
        _requester(row, user)
        if row.version != expected_version:
            raise HTTPException(409, "Workflow version changed")
        if row.status != "ready":
            return runtime.response(row)
        row.state = {**row.state, "runtime_user_id": user.user_id}
        await runtime.authorized_actor(row)
        await runtime.credential_metadata(
            session, row.organization_id, row.state["credential_id"], row.state["url"], row.state["credential_revision"]
        )
        native_status = await session.scalar(
            select(WorkflowRunModel.status).where(
                WorkflowRunModel.workflow_run_id == row.workflow_run_id, WorkflowRunModel.organization_id == user.org_id
            )
        )
        existing_block = await session.scalar(
            select(WorkflowRunBlockModel.workflow_run_block_id)
            .where(
                WorkflowRunBlockModel.workflow_run_id == row.workflow_run_id,
                WorkflowRunBlockModel.organization_id == user.org_id,
            )
            .limit(1)
        )
        if native_status != "created" or existing_block is not None:
            row.status = "needs_human"
            row.version += 1
            runtime.audit(session, row, "native_start_uncertain")
            await session.commit()
            return runtime.response(row)
        row.status = "running"
        row.version += 1
        runtime.audit(session, row, "workflow_dispatched")
        await session.commit()
        result = runtime.response(row)
        workflow_id, run_id = row.workflow_id, row.workflow_run_id
    organization = await forge_app.DATABASE.get_organization(user.org_id)
    try:
        workflow = await forge_app.WORKFLOW_SERVICE.get_workflow(workflow_id, organization_id=user.org_id)
        await AsyncExecutorFactory.get_executor().execute_workflow(
            request=request,
            background_tasks=background_tasks,
            organization=organization,
            workflow_id=workflow_id,
            workflow_run_id=run_id,
            workflow_permanent_id=workflow.workflow_permanent_id,
            max_steps_override=50,
            browser_session_id=None,
            api_key=None,
            block_labels=None,
            block_outputs=None,
        )
    except Exception:
        # Ambiguous dispatch never returns provider exception text or retries a browser action.
        async with forge_app.DATABASE.Session() as session:
            row = await _scoped_instance(session, instance_id, user, lock=True)
            if row.status not in ("completed", "terminated", "needs_human"):
                row.status = "needs_human"
                row.version += 1
                runtime.audit(session, row, "dispatch_uncertain")
                await session.commit()
            return runtime.response(row)
    return result


@router.post("/instantiate/{template_id}")
async def instantiate_template(
    template_id: str,
    body: InstantiateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
    user: UserContext = Depends(require_any_operator),
):
    template = get_template(template_id)
    if template is None:
        raise HTTPException(404, "Workflow template not found")
    _development_guard()
    try:
        compiled = compile_native_template(template, body.parameters)
        steps = build_skill_pipeline(template, body.parameters)
    except (ValueError, KeyError, StopIteration):
        raise HTTPException(422, "Invalid controlled template parameters; use a credential reference") from None
    url = compiled.workflow_definition.blocks[0].url
    if url not in procurement_routes._allowed_smoke_urls():
        raise HTTPException(403, "Template URL is not controlled")
    await procurement_routes._validate_smoke_context(
        procurement_routes.SmokeTaskRequest(
            organization_id=user.org_id, department_id=body.department_id, category_id=body.category_id, url=url
        ),
        user,
    )
    request_hash = runtime.digest({"template_id": template_id, "body": body.model_dump(), "user_id": user.user_id})
    key_hash = runtime.digest(idempotency_key)
    async with forge_app.DATABASE.Session() as session:
        existing = await session.scalar(
            select(Instance).where(Instance.organization_id == user.org_id, Instance.idempotency_hash == key_hash)
        )
        if existing is not None:
            _requester(existing, user)
            if existing.request_hash != request_hash:
                raise HTTPException(409, "Idempotency key belongs to another request")
            return runtime.response(existing)
        revision = await runtime.credential_metadata(session, user.org_id, body.parameters["credential_id"], url)
        labels = tuple(block.label for block in compiled.workflow_definition.blocks)
        plan = await runtime.plan_steps(labels, completed=[])
        row = Instance(
            organization_id=user.org_id,
            department_id=body.department_id,
            category_id=body.category_id,
            created_by=user.user_id,
            template_id=template_id,
            idempotency_hash=key_hash,
            request_hash=request_hash,
            status="preparing",
            version=1,
            state={
                "credential_id": body.parameters["credential_id"],
                "credential_revision": revision,
                "url": url,
                "plan": plan,
                "steps": [dict(label=label, status="pending", task_id=None, artifact_ids=[]) for label in labels],
                "headers": {
                    f"table_extract_{i}": step.params.get("headers", [])
                    for i, step in enumerate(steps)
                    if step.skill_name == "table_extract"
                },
            },
        )
        session.add(row)
        try:
            await session.flush()
            runtime.audit(session, row, "workflow_preparing")
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(
                select(Instance).where(Instance.organization_id == user.org_id, Instance.idempotency_hash == key_hash)
            )
            if existing is None or existing.request_hash != request_hash:
                raise HTTPException(409, "Concurrent workflow request conflict") from None
            return runtime.response(existing)
        instance_id = row.instance_id
    try:
        organization = await forge_app.DATABASE.get_organization(user.org_id)
        workflow = await forge_app.WORKFLOW_SERVICE.create_workflow_from_request(organization, compiled)
        native = await prepare_workflow(
            workflow.workflow_permanent_id,
            organization,
            WorkflowRequestBody(data={}),
            version=workflow.version,
            max_steps=50,
        )
        async with forge_app.DATABASE.Session() as session:
            row = await _scoped_instance(session, instance_id, user, lock=True)
            if row.status != "preparing":
                raise HTTPException(409, "Workflow preparation changed")
            row.workflow_id = workflow.workflow_id
            row.workflow_run_id = native.workflow_run_id
            row.state = {
                **row.state,
                "workflow_digest": runtime.digest(workflow.workflow_definition.model_dump(mode="json")),
            }
            row.status = "ready"
            row.version += 1
            runtime.audit(session, row, "workflow_ready")
            await session.commit()
            version = row.version
    except Exception:
        async with forge_app.DATABASE.Session() as session:
            row = await _scoped_instance(session, instance_id, user, lock=True)
            if row.status not in ("completed", "terminated", "needs_human"):
                row.status = "needs_human"
                row.version += 1
                runtime.audit(session, row, "preparation_uncertain")
                await session.commit()
            return runtime.response(row)
    return await _dispatch(instance_id, user, request, background_tasks, version)


@router.get("/instances/{instance_id}")
async def get_instance(instance_id: str, user: CurrentUser):
    async with forge_app.DATABASE.Session() as session:
        return runtime.response(await _scoped_instance(session, instance_id, user))


class RecoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


@router.post("/instances/{instance_id}/recover")
async def recover_instance(
    instance_id: str,
    body: RecoverRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(require_any_operator),
):
    _development_guard()
    async with forge_app.DATABASE.Session() as session:
        row = await _scoped_instance(session, instance_id, user, lock=True)
        _requester(row, user)
        if row.version != body.expected_version:
            raise HTTPException(409, "Workflow version changed")
        if row.status == "ready":
            pass  # Only a committed, undispatched run can start.
        elif row.status in ("preparing", "running"):
            row.status = "needs_human"
            row.version += 1
            runtime.audit(session, row, "recovery_ambiguous")
            await session.commit()
            return runtime.response(row)
        else:
            return runtime.response(row)
    return await _dispatch(instance_id, user, request, background_tasks, body.expected_version)


@router.post("/instances/{instance_id}/terminate")
async def terminate_instance(instance_id: str, body: RecoverRequest, user: UserContext = Depends(require_any_operator)):
    _development_guard()
    async with forge_app.DATABASE.Session() as session:
        row = await _scoped_instance(session, instance_id, user, lock=True)
        _requester(row, user)
        if row.version != body.expected_version or row.status == "completed":
            raise HTTPException(409, "Workflow version or terminal state changed")
        if row.status != "terminated":
            if row.workflow_run_id:
                await session.execute(
                    update(WorkflowRunModel)
                    .where(
                        WorkflowRunModel.workflow_run_id == row.workflow_run_id,
                        WorkflowRunModel.organization_id == user.org_id,
                    )
                    .values(status="canceled")
                )
                await session.execute(
                    update(TaskModel)
                    .where(
                        TaskModel.workflow_run_id == row.workflow_run_id,
                        TaskModel.organization_id == user.org_id,
                        TaskModel.status.in_(("created", "queued", "running")),
                    )
                    .values(status="canceled")
                )
            row.state = {**row.state, "runtime_user_id": user.user_id}
            row.status = "terminated"
            row.version += 1
            runtime.audit(session, row, "workflow_terminated")
            await session.commit()
        return runtime.response(row)
