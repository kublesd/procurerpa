"""Disposable PostgreSQL + actual native converter/block service; synthetic browser/vault boundaries."""

import datetime
import importlib.util
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from sqlalchemy import event, select, update

from enterprise.agent import quote_planner
from enterprise.audit.models import AuditLogModel
from enterprise.auth import dependencies
from enterprise.auth.models import BusinessLineModel
from enterprise.workflows import routes, runtime
from enterprise.workflows.models import WorkflowInstanceModel as Instance
from skyvern.forge.sdk.db.models import (
    ArtifactModel,
    Base,
    CredentialModel,
    TaskModel,
    WorkflowModel,
    WorkflowRunBlockModel,
    WorkflowRunModel,
)
from skyvern.forge.sdk.schemas.credentials import PasswordCredential
from skyvern.forge.sdk.workflow import context_manager as native_context
from skyvern.forge.sdk.workflow import service as native_service
from skyvern.forge.sdk.workflow.models import block as native_block
from skyvern.forge.sdk.workflow.models.parameter import CredentialParameter, OutputParameter, WorkflowParameter
from skyvern.forge.sdk.workflow.models.workflow import Workflow, WorkflowRun
from skyvern.forge.sdk.workflow.workflow_definition_converter import convert_workflow_definition
from skyvern.services import workflow_service as native_prepare
from tests.integration import test_approval01
from tests.unit.test_day_11_quotes import _user

approval_database = test_approval01.database
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.environ.get("RUN01_TEST_DATABASE_URL"), reason="Requires disposable PostgreSQL"),
]
URL = "http://localhost:18080/controlled-portal"
PARAMS = dict(
    supplier_portal_url=URL,
    credential_id="cred_demo",
    supplier_code="demo-supplier",
    material_code="demo-material",
    start_date="2026-01-01",
    end_date="2026-01-02",
)


@pytest_asyncio.fixture
async def harness(approval_database, monkeypatch):
    engine, sessions = approval_database
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda conn: Base.metadata.create_all(
                conn,
                tables=[
                    BusinessLineModel.__table__,
                    Base.metadata.tables["folders"],
                    CredentialModel.__table__,
                    WorkflowModel.__table__,
                    WorkflowRunModel.__table__,
                    WorkflowRunBlockModel.__table__,
                    Instance.__table__,
                ],
            )
        )
    async with sessions() as session:
        session.add(
            CredentialModel(
                credential_id="cred_demo",
                organization_id="org_a",
                vault_type="custom",
                item_id="synthetic-item",
                credential_type="password",
                name="synthetic",
                tested_url=URL,
            )
        )
        await session.commit()
    facts = SimpleNamespace(
        executions=0, blocks=[], missing_artifact=False, invalid_table=False, rotate_after_login=False, vault_calls=0
    )
    workflows = {}

    async def get_run(workflow_run_id, organization_id=None):
        async with sessions() as session:
            row = await session.scalar(
                select(WorkflowRunModel).where(WorkflowRunModel.workflow_run_id == workflow_run_id)
            )
            if row is None or organization_id and row.organization_id != organization_id:
                return None
            return WorkflowRun.model_validate(
                {column.name: getattr(row, column.name) for column in row.__table__.columns}
            )

    async def update_run(workflow_run_id, **values):
        async with sessions() as session:
            values = {
                key: value
                for key, value in values.items()
                if key in WorkflowRunModel.__table__.columns and value is not None
            }
            await session.execute(
                update(WorkflowRunModel).where(WorkflowRunModel.workflow_run_id == workflow_run_id).values(**values)
            )
            await session.commit()
        return await get_run(workflow_run_id)

    async def get_credential(credential_id, organization_id):
        async with sessions() as session:
            row = await session.scalar(
                select(CredentialModel).where(
                    CredentialModel.credential_id == credential_id,
                    CredentialModel.organization_id == organization_id,
                    CredentialModel.deleted_at.is_(None),
                )
            )
            return (
                None
                if row is None
                else SimpleNamespace(vault_type="custom", totp_identifier=None, browser_profile_id=None)
            )

    async def vault_item(_credential):
        facts.vault_calls += 1
        return SimpleNamespace(
            credential=PasswordCredential(username="synthetic-private-user", password="synthetic-private-password")
        )

    manager = SimpleNamespace(workflow_run_contexts={})
    manager.get_workflow_run_context = lambda run_id: manager.workflow_run_contexts[run_id]

    async def register(run_id, parameters, organization):
        await manager.workflow_run_contexts[run_id].register_block_parameters(None, parameters, organization)

    manager.register_block_parameters_for_workflow_run = register
    database = SimpleNamespace(
        Session=sessions,
        get_organization=AsyncMock(side_effect=lambda org: SimpleNamespace(organization_id=org)),
        get_workflow_run=get_run,
        update_workflow_run=update_run,
        get_credential=get_credential,
        create_task_run=AsyncMock(),
    )
    app = SimpleNamespace(
        DATABASE=database,
        CREDENTIAL_VAULT_SERVICES={"custom": SimpleNamespace(get_credential_item=vault_item)},
        WORKFLOW_CONTEXT_MANAGER=manager,
    )
    for module, name in [
        (routes, "forge_app"),
        (runtime, "app"),
        (native_service, "app"),
        (native_prepare, "app"),
        (native_context, "app"),
        (native_block, "app"),
        (dependencies, "forge_app"),
    ]:
        monkeypatch.setattr(module, name, app)
    monkeypatch.setattr(routes, "is_development_environment", lambda _env: True)
    monkeypatch.setattr(routes.procurement_routes, "_allowed_smoke_urls", lambda: {URL})
    monkeypatch.setattr(
        quote_planner,
        "call_quote_planner",
        AsyncMock(side_effect=lambda prompt: {"steps": json.loads(prompt.split("\n")[-1])["remaining"]}),
    )

    async def create_workflow(organization, request):
        workflow_id = "wf_" + uuid4().hex
        definition = convert_workflow_definition(request.workflow_definition, workflow_id)
        now = datetime.datetime.now(datetime.UTC)
        wf = Workflow(
            workflow_id=workflow_id,
            organization_id=organization.organization_id,
            workflow_permanent_id="wp_" + uuid4().hex,
            version=1,
            is_saved_task=False,
            title=request.title,
            description=request.description,
            workflow_definition=definition,
            created_at=now,
            modified_at=now,
            run_with="agent",
        )
        workflows[workflow_id] = wf
        async with sessions() as session:
            session.add(
                WorkflowModel(
                    workflow_id=workflow_id,
                    organization_id=wf.organization_id,
                    workflow_permanent_id=wf.workflow_permanent_id,
                    version=1,
                    is_saved_task=False,
                    title=wf.title,
                    description=wf.description,
                    workflow_definition=definition.model_dump(mode="json"),
                    status="published",
                )
            )
            await session.commit()
        return wf

    async def get_workflow(workflow_id, organization_id=None):
        return workflows[workflow_id]

    async def get_permanent(workflow_permanent_id, **_kwargs):
        return next(wf for wf in workflows.values() if wf.workflow_permanent_id == workflow_permanent_id)

    async def setup_workflow_run(workflow_permanent_id, organization, **_kwargs):
        wf = await get_permanent(workflow_permanent_id)
        async with sessions() as session:
            run = WorkflowRunModel(
                workflow_id=wf.workflow_id,
                workflow_permanent_id=wf.workflow_permanent_id,
                organization_id=organization.organization_id,
                status="created",
            )
            session.add(run)
            await session.commit()
            run_id = run.workflow_run_id
        return await get_run(run_id)

    service = native_service.WorkflowService.__new__(native_service.WorkflowService)
    monkeypatch.setattr(service, "_resolve_login_block_browser_profile_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_generate_pending_script_for_block", AsyncMock())
    app.WORKFLOW_SERVICE = SimpleNamespace(
        create_workflow_from_request=create_workflow,
        setup_workflow_run=setup_workflow_run,
        get_workflow=get_workflow,
        get_workflow_by_permanent_id=get_permanent,
    )

    async def synthetic_browser(self, workflow_run_id, organization_id, **_kwargs):
        facts.blocks.append(self.label)
        task_id, block_id = "tsk_" + uuid4().hex, "wrb_" + uuid4().hex
        async with sessions() as session:
            session.add(
                TaskModel(
                    task_id=task_id,
                    workflow_run_id=workflow_run_id,
                    organization_id=organization_id,
                    status="completed",
                    url=URL,
                    extracted_information={"rows": []} if not facts.invalid_table else {},
                )
            )
            session.add(
                WorkflowRunBlockModel(
                    workflow_run_block_id=block_id,
                    workflow_run_id=workflow_run_id,
                    organization_id=organization_id,
                    label=self.label,
                    block_type=self.block_type,
                    task_id=task_id,
                    status="completed",
                )
            )
            if not facts.missing_artifact:
                session.add(
                    ArtifactModel(
                        task_id=task_id,
                        organization_id=organization_id,
                        artifact_type="html_scrape",
                        uri="synthetic://evidence",
                    )
                )
            if facts.rotate_after_login and self.label == "login_0":
                await session.execute(
                    update(CredentialModel)
                    .where(CredentialModel.credential_id == "cred_demo")
                    .values(modified_at=datetime.datetime(2030, 1, 1))
                )
            await session.commit()
        return native_block.BlockResult(
            success=True,
            status="completed",
            workflow_run_block_id=block_id,
            output_parameter=self.output_parameter,
            output_parameter_value={"downloaded_files": [{"id": "synthetic-file"}]},
        )

    monkeypatch.setattr(native_block.BaseTaskBlock, "execute_safe", synthetic_browser)

    async def execute(workflow_run_id, workflow_id, organization, **_kwargs):
        wf = workflows[workflow_id]
        regular = [
            (p, SimpleNamespace(value=p.default_value))
            for p in wf.workflow_definition.parameters
            if isinstance(p, WorkflowParameter)
        ]
        outputs = [p for p in wf.workflow_definition.parameters if isinstance(p, OutputParameter)]
        secrets = [p for p in wf.workflow_definition.parameters if isinstance(p, CredentialParameter)]
        ctx = await native_context.WorkflowRunContext.init(
            None,
            organization,
            workflow_run_id,
            wf.title,
            wf.workflow_id,
            wf.workflow_permanent_id,
            regular,
            outputs,
            [],
            secrets,
            workflow=wf,
        )
        manager.workflow_run_contexts[workflow_run_id] = ctx
        run = await update_run(workflow_run_id, status="running")
        for i, block in enumerate(wf.workflow_definition.blocks):
            run, _, _, stop, _ = await service._execute_single_block(
                workflow=wf,
                block=block,
                block_idx=i,
                blocks_cnt=len(wf.workflow_definition.blocks),
                workflow_run=run,
                organization=organization,
                workflow_run_id=workflow_run_id,
                browser_session_id=None,
                script_blocks_by_label={},
                loaded_script_module=None,
                is_script_run=False,
                blocks_to_update=set(),
            )
            if stop:
                break

    async def dispatch(**kwargs):
        facts.executions += 1
        kwargs["background_tasks"].add_task(
            execute,
            workflow_run_id=kwargs["workflow_run_id"],
            workflow_id=kwargs["workflow_id"],
            organization=kwargs["organization"],
        )

    monkeypatch.setattr(
        routes.AsyncExecutorFactory, "get_executor", staticmethod(lambda: SimpleNamespace(execute_workflow=dispatch))
    )
    web = FastAPI()
    web.include_router(routes.router, prefix="/api/v1")
    web.dependency_overrides[dependencies.get_current_user] = _user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=web), base_url="http://test") as client:
        yield engine, sessions, facts, client, workflows, manager


async def start(client, key="demo", parameters=None):
    return await client.post(
        "/api/v1/enterprise/workflows/instantiate/tpl_supplier_quote_ledger",
        headers={"Idempotency-Key": key},
        json=dict(department_id="dept_a", category_id="pc_a", parameters=parameters or PARAMS),
    )


async def test_native_steps_restart_idempotency_safe_audit_and_artifact(harness):
    engine, sessions, facts, client, workflows, manager = harness
    initial = await start(client)
    assert initial.status_code == 200, initial.text
    instance_id = initial.json()["instance_id"]
    await engine.dispose()
    state = (await client.get(f"/api/v1/enterprise/workflows/instances/{instance_id}")).json()
    assert state["status"] == "completed", state
    assert len(state["steps"]) == 4 and all(
        step["status"] == "completed" and step["artifact_ids"] for step in state["steps"]
    )
    assert state["plan"]["steps"] == [] and len(state["plan"]["completed"]) == 4
    repeat = await start(client)
    assert repeat.json()["instance_id"] == instance_id and facts.executions == 1 and len(facts.blocks) == 4
    async with sessions() as session:
        logs = (
            await session.scalars(select(AuditLogModel).where(AuditLogModel.business_object_id == instance_id))
        ).all()
        row = await session.get(Instance, instance_id)
        evidence = state | {"persisted": row.state, "logs": [log.target_element for log in logs]}
        assert len(logs) == 11  # prepare, ready, dispatch, two events per native block
        assert "synthetic-private" not in json.dumps(evidence)
    assert facts.vault_calls == 1
    conflict = await start(client, parameters={**PARAMS, "material_code": "other"})
    assert conflict.status_code == 409 and facts.executions == 1


@pytest.mark.parametrize("change", ["deleted", "org", "purpose", "provider", "missing"])
async def test_credential_failure_prevents_native_creation(harness, change):
    _engine, sessions, facts, client, workflows, _manager = harness
    async with sessions() as session:
        values = {
            "deleted": dict(deleted_at=datetime.datetime.now(datetime.UTC).replace(tzinfo=None)),
            "org": dict(organization_id="org_b"),
            "purpose": dict(tested_url="http://other"),
            "provider": dict(vault_type="azure_vault"),
            "missing": dict(credential_id="cred_missing"),
        }[change]
        await session.execute(
            update(CredentialModel).where(CredentialModel.credential_id == "cred_demo").values(**values)
        )
        await session.commit()
    response = await start(client)
    assert response.status_code == 409 and not workflows and facts.executions == 0 and facts.vault_calls == 0


@pytest.mark.parametrize("failure", ["missing_artifact", "invalid_table", "rotate_after_login"])
async def test_evidence_or_credential_failure_stops_native_steps_and_never_replays(harness, failure):
    _engine, sessions, facts, client, _workflows, _manager = harness
    setattr(facts, failure, True)
    result = await start(client)
    instance_id = result.json()["instance_id"]
    state = (await client.get(f"/api/v1/enterprise/workflows/instances/{instance_id}")).json()
    assert state["status"] == "needs_human", state
    before = list(facts.blocks)
    recovered = await client.post(
        f"/api/v1/enterprise/workflows/instances/{instance_id}/recover", json={"expected_version": state["version"]}
    )
    assert recovered.json()["status"] == "needs_human" and facts.blocks == before and facts.executions == 1
    stale = await client.post(
        f"/api/v1/enterprise/workflows/instances/{instance_id}/terminate", json={"expected_version": 1}
    )
    assert stale.status_code == 409
    done = await client.post(
        f"/api/v1/enterprise/workflows/instances/{instance_id}/terminate", json={"expected_version": state["version"]}
    )
    assert done.json()["status"] == "terminated"


async def test_native_step_and_audit_roll_back_together(harness):
    engine, sessions, facts, client, workflows, _manager = harness
    result = await start(client)
    instance_id = result.json()["instance_id"]
    async with sessions() as session:
        row = await session.get(Instance, instance_id)
        state = dict(row.state)
        steps = [dict(step) for step in state["steps"]]
        steps[-1]["status"] = "running"
        row.state = {**state, "steps": steps}
        row.status = "running"
        await session.commit()
        run_id, workflow = row.workflow_run_id, workflows[row.workflow_id]
        native = await session.scalar(
            select(WorkflowRunBlockModel).where(
                WorkflowRunBlockModel.workflow_run_id == run_id, WorkflowRunBlockModel.label == steps[-1]["label"]
            )
        )

    def fail(_conn, _cursor, statement, _params, _context, _many):
        if statement.startswith("INSERT INTO audit_logs"):
            raise RuntimeError("synthetic audit failure")

    event.listen(engine.sync_engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="synthetic audit failure"):
            await runtime.after_native_block(
                workflow,
                run_id,
                "org_a",
                steps[-1]["label"],
                SimpleNamespace(
                    status="completed",
                    workflow_run_block_id=native.workflow_run_block_id,
                    output_parameter_value={"downloaded_files": [{}]},
                ),
            )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fail)
    async with sessions() as session:
        row = await session.get(Instance, instance_id)
        assert row.status == "running" and row.state["steps"][-1]["status"] == "running"
    state = (await client.get(f"/api/v1/enterprise/workflows/instances/{instance_id}")).json()
    await client.post(
        f"/api/v1/enterprise/workflows/instances/{instance_id}/recover", json={"expected_version": state["version"]}
    )
    assert facts.executions == 1


async def test_migration_upgrade_and_downgrade_matches_instance_model(harness):
    engine, *_ = harness
    spec = importlib.util.spec_from_file_location(
        "stage4_migration", "alembic/versions/2026_09_30_0013_workflow_instances.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    async with engine.begin() as connection:

        def check(conn):
            migration.op = Operations(MigrationContext.configure(conn))
            migration.downgrade()
            migration.upgrade()

        await connection.run_sync(check)
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: Instance.__table__.drop(conn))


async def test_cross_org_requester_revocation_and_stale_recovery(harness):
    _engine, sessions, facts, client, workflows, manager = harness
    first = await start(client)
    instance_id = first.json()["instance_id"]
    async with sessions() as session:
        row = await session.get(Instance, instance_id)
        row.status = "ready"
        row.state = {**row.state, "steps": [{**step, "status": "pending"} for step in row.state["steps"]]}
        await session.commit()
        version, run_id = row.version, row.workflow_run_id
    other = _user().model_copy(update={"org_id": "org_b"})
    with pytest.raises(Exception) as error:
        await routes.get_instance(instance_id, other)
    assert error.value.status_code == 404
    stale = await client.post(
        f"/api/v1/enterprise/workflows/instances/{instance_id}/recover", json={"expected_version": version - 1}
    )
    assert stale.status_code == 409 and facts.executions == 1
    from enterprise.auth.models import EnterpriseUserModel

    async with sessions() as session:
        await session.execute(
            update(EnterpriseUserModel).where(EnterpriseUserModel.user_id == "user_a").values(is_active=False)
        )
        await session.commit()
    denied = await client.post(
        f"/api/v1/enterprise/workflows/instances/{instance_id}/recover", json={"expected_version": version}
    )
    assert denied.status_code == 403 and facts.executions == 1
    with pytest.raises(Exception):
        await runtime.check_secret_input(manager.workflow_run_contexts[run_id], "http://foreign")


async def test_concurrent_idempotency_and_ambiguous_recovery_are_single_execution(harness):
    import asyncio

    _engine, sessions, facts, client, _workflows, _manager = harness
    a, b = await asyncio.gather(start(client, "concurrent"), start(client, "concurrent"))
    assert a.status_code == b.status_code == 200 and a.json()["instance_id"] == b.json()["instance_id"]
    assert facts.executions == 1
    instance_id = a.json()["instance_id"]
    async with sessions() as session:
        row = await session.get(Instance, instance_id)
        row.status = "running"
        await session.commit()
        version = row.version
    recovered = await client.post(
        f"/api/v1/enterprise/workflows/instances/{instance_id}/recover", json={"expected_version": version}
    )
    assert recovered.json()["status"] == "needs_human" and facts.executions == 1


async def test_bad_template_inputs_never_reach_vault_or_native_runtime(harness, monkeypatch):
    _engine, _sessions, facts, client, workflows, _manager = harness
    for params in [
        {**PARAMS, "password": "synthetic-private-password"},
        {**PARAMS, "supplier_portal_url": "http://foreign"},
        {**PARAMS, "credential_id": "vault:raw"},
    ]:
        response = await start(client, parameters=params)
        assert response.status_code in (422, 403)
        assert "synthetic-private" not in response.text
    monkeypatch.setattr(routes, "is_development_environment", lambda _env: False)
    assert (await start(client)).status_code == 404
    assert not workflows and facts.vault_calls == facts.executions == 0


async def test_undispatched_ready_instance_recovers_once_without_repeating_completed_native_step(harness, monkeypatch):
    _engine, sessions, facts, client, _workflows, _manager = harness
    actual = routes._dispatch

    async def leave_ready(instance_id, user, *_args):
        return await routes.get_instance(instance_id, user)

    monkeypatch.setattr(routes, "_dispatch", leave_ready)
    initial = await start(client)
    assert initial.json()["status"] == "ready" and facts.executions == 0
    monkeypatch.setattr(routes, "_dispatch", actual)
    instance_id = initial.json()["instance_id"]
    recovered = await client.post(
        f"/api/v1/enterprise/workflows/instances/{instance_id}/recover",
        json={"expected_version": initial.json()["version"]},
    )
    assert recovered.status_code == 200 and facts.executions == 1
    state = (await client.get(f"/api/v1/enterprise/workflows/instances/{instance_id}")).json()
    assert state["status"] == "completed" and len(facts.blocks) == 4


async def test_invalid_persisted_plan_stops_before_native_browser_action(harness, monkeypatch):
    _engine, sessions, facts, client, _workflows, _manager = harness
    actual = routes._dispatch

    async def leave_ready(instance_id, user, *_args):
        return await routes.get_instance(instance_id, user)

    monkeypatch.setattr(routes, "_dispatch", leave_ready)
    initial = await start(client)
    instance_id = initial.json()["instance_id"]
    async with sessions() as session:
        row = await session.get(Instance, instance_id)
        row.state = {**row.state, "plan": {**row.state["plan"], "steps": []}}
        await session.commit()
    monkeypatch.setattr(routes, "_dispatch", actual)
    recovered = await client.post(
        f"/api/v1/enterprise/workflows/instances/{instance_id}/recover",
        json={"expected_version": initial.json()["version"]},
    )
    assert recovered.status_code == 200
    state = (await client.get(f"/api/v1/enterprise/workflows/instances/{instance_id}")).json()
    assert state["status"] == "needs_human" and facts.blocks == [] and facts.executions == 1


async def test_termination_during_preparation_is_not_overwritten_by_failure(harness, monkeypatch):
    _engine, sessions, facts, client, _workflows, _manager = harness

    async def interrupted(*_args, **_kwargs):
        async with sessions() as session:
            row = await session.scalar(select(Instance))
            stopped = await routes.terminate_instance(
                row.instance_id, routes.RecoverRequest(expected_version=row.version), _user()
            )
            assert stopped["status"] == "terminated"
        raise RuntimeError("synthetic interrupted preparation")

    monkeypatch.setattr(routes.forge_app.WORKFLOW_SERVICE, "create_workflow_from_request", interrupted)
    response = await start(client)
    assert response.status_code == 200 and response.json()["status"] == "terminated"
    assert facts.executions == facts.vault_calls == 0
