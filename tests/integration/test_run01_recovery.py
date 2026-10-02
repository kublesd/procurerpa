"""Opt-in PostgreSQL process-crash checks; no browser, provider, or production data.

RUN01_TEST_DATABASE_URL must point at disposable localhost PostgreSQL on 55439 or 15439.
Each scenario owns a fresh schema and tests the real route, SQL locks and quote writes.
"""

import asyncio
import os
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from enterprise.approval import routes as approvals
from enterprise.approval.models import ApprovalRequestModel
from enterprise.audit import logger as audit_logger
from enterprise.audit.models import AuditLogModel
from enterprise.auth.models import DepartmentModel, EnterpriseUserModel, TaskExtensionModel
from enterprise.procurement import routes
from enterprise.procurement.models import (
    ProcurementCategoryModel,
    ProcurementCoordinationStateModel,
    ProcurementHumanReviewModel,
    SupplierQuoteModel,
)
from skyvern.forge.sdk.db.models import ArtifactModel, Base, OrganizationModel, TaskModel
from skyvern.forge.sdk.schemas.tasks import TaskStatus
from tests.unit.test_day_11_quotes import _user


def _engine(schema):
    url = make_url(os.environ["RUN01_TEST_DATABASE_URL"])
    assert url.host in ("localhost", "127.0.0.1") and url.port in (55439, 15439)
    assert schema.startswith("run01_test_") and schema.removeprefix("run01_test_").isalnum()
    return create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})


def _install(engine, monkeypatch, crash=None):
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    from enterprise.agent import quote_planner

    async def planner(prompt):
        import json
        return {"steps": json.loads(prompt.split("\n")[-1])["remaining"]}

    monkeypatch.setattr(quote_planner, "call_quote_planner", planner)

    def interrupt(stage):
        if crash == stage:
            print("CLAIMED", flush=True)
            sys.stdin.readline()
            os._exit(71)  # Deliberately bypass context managers and connection cleanup.

    async def get_task(task_id, organization_id):
        async with sessions() as session:
            task = await session.scalar(select(TaskModel).where(
                TaskModel.task_id == task_id, TaskModel.organization_id == organization_id,
            ))
            values = {column.name: getattr(task, column.name) for column in TaskModel.__table__.columns}
            values["status"] = TaskStatus(values["status"])
            return SimpleNamespace(**values)

    async def update_task(task_id, organization_id, status):
        interrupt("before")
        async with sessions() as session:
            await session.execute(update(TaskModel).where(
                TaskModel.task_id == task_id, TaskModel.organization_id == organization_id,
            ).values(status=status))
            await session.commit()

    class Executor:
        async def execute_task(self, **kwargs):
            async def execute():
                interrupt("running")
                await update_task("task_a", "org_a", TaskStatus.completed)
            kwargs["background_tasks"].add_task(execute)

    original_advance = routes.advance_quote_state

    async def advance(session, **kwargs):
        if kwargs["step"] == "running":
            interrupt("before")
        return await original_advance(session, **kwargs)

    monkeypatch.setattr(routes, "advance_quote_state", advance)
    original_persist = routes._persist_extracted_quote

    async def persist(*args):
        interrupt("completed")
        return await original_persist(*args)

    app = SimpleNamespace(DATABASE=SimpleNamespace(Session=sessions, get_task=get_task, update_task=update_task))
    monkeypatch.setattr(routes, "forge_app", app)
    monkeypatch.setattr(approvals, "forge_app", app)
    monkeypatch.setattr(audit_logger, "forge_app", app)
    monkeypatch.setattr(routes.AsyncExecutorFactory, "get_executor", staticmethod(lambda: Executor()))
    monkeypatch.setattr(routes, "_persist_extracted_quote", persist)
    return sessions


async def _seed(engine, approved):
    tables = set()

    def include(table):
        if table in tables:
            return
        tables.add(table)
        for key in table.foreign_keys:
            include(key.column.table)

    for model in (TaskExtensionModel, SupplierQuoteModel, ProcurementHumanReviewModel, ProcurementCoordinationStateModel, ApprovalRequestModel, AuditLogModel):
        include(model.__table__)
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: Base.metadata.create_all(sync, tables=list(tables)))
        for model, values in (
            (OrganizationModel, dict(organization_id="org_a", organization_name="Synthetic RUN01")),
            (DepartmentModel, dict(department_id="dept_a", organization_id="org_a", department_name="Synthetic", department_code="test")),
            (EnterpriseUserModel, dict(user_id="user_a", organization_id="org_a", username="synthetic", password_hash="not-a-login", display_name="Synthetic")),
            (ProcurementCategoryModel, dict(category_id="pc_a", organization_id="org_a", category_name="Synthetic", category_code="test")),
            (TaskModel, dict(
                task_id="task_a", organization_id="org_a", status="created", url="https://supplier.example/quote",
                data_extraction_goal=routes._QUOTE_EXTRACTION_GOAL, extracted_information_schema=routes.QUOTE_EXTRACTION_SCHEMA,
                extracted_information=dict(supplier_id="synthetic", material_name="SSD", quantity=10, unit="unit", currency="CNY",
                                           unit_price_cny=10, freight_cny=0, moq=1, delivery_days=5, confidence=0.95),
            )),
            (TaskExtensionModel, dict(task_id="task_a", organization_id="org_a", department_id="dept_a", category_id="pc_a", created_by="user_a", risk_level="high" if approved else "low")),
            (ArtifactModel, dict(artifact_id="artifact_a", task_id="task_a", organization_id="org_a", artifact_type="html_scrape", uri="synthetic://evidence")),
        ):
            await connection.execute(model.__table__.insert().values(**values))
        if approved:
            await connection.execute(ApprovalRequestModel.__table__.insert().values(
                approval_id="apr_a", task_id="task_a", organization_id="org_a", department_id="dept_a",
                requester_user_id="user_a", risk_level="high", risk_reason="synthetic", approver_department_id="dept_a", status="approved",
            ))


_CHILD = """
import os, sys, types, runpy
sys.path[:] = os.environ['RUN01_TEST_PYTHONPATH'].split(os.pathsep) + sys.path
import dotenv, dotenv.main
dotenv.load_dotenv = dotenv.main.load_dotenv = lambda *a, **k: False
dotenv.dotenv_values = dotenv.main.dotenv_values = lambda *a, **k: {}
factory = types.ModuleType('skyvern.forge.sdk.executor.factory')
factory.AsyncExecutorFactory = type('AsyncExecutorFactory', (), {'get_executor': staticmethod(lambda: None)})
sys.modules[factory.__name__] = factory
runpy.run_module('tests.integration.test_run01_recovery', run_name='__main__')
"""


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get("RUN01_TEST_DATABASE_URL"), reason="Requires disposable RUN01 PostgreSQL")
@pytest.mark.parametrize("stage", ["before", "running", "completed"])
@pytest.mark.parametrize("approved", [False, True])
async def test_process_crash_releases_exclusive_claim(monkeypatch, stage, approved):
    schema = "run01_test_" + uuid4().hex
    engine = _engine(schema)
    child = None
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await _seed(engine, approved)
        sessions = _install(engine, monkeypatch)
        async def recover():
            if approved:
                return await approvals.continue_request("apr_a", BackgroundTasks(), _user())
            return await routes.recover_quote_task("task_a", _user())

        environment = dict(os.environ, RUN01_TEST_PYTHONPATH=os.pathsep.join(sys.path))
        child = subprocess.Popen([sys.executable, "-c", _CHILD, schema, stage], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment)
        line = await asyncio.wait_for(asyncio.to_thread(child.stdout.readline), timeout=20)
        assert line.strip() == "CLAIMED", child.stderr.read() if child.poll() is not None else line
        with pytest.raises(HTTPException) as busy:
            await recover()
        assert busy.value.status_code == 409
        child.stdin.write("crash\n")
        child.stdin.flush()
        assert await asyncio.to_thread(child.wait, 10) == 71
        # PostgreSQL may observe the TCP disconnect slightly after Windows reports process exit.
        async with asyncio.timeout(10):
            while True:
                async with sessions() as session:
                    released = await session.scalar(select(TaskExtensionModel).where(
                        TaskExtensionModel.task_id == "task_a",
                    ).with_for_update(skip_locked=True))
                if released is not None:
                    break
                await asyncio.sleep(0.05)
        if stage == "running":
            with pytest.raises(HTTPException) as interrupted:
                await recover()
            assert interrupted.value.status_code == 422
            assert interrupted.value.detail["reason_code"] == "quote_execution_interrupted"
            async with sessions() as session:
                review = await session.scalar(select(ProcurementHumanReviewModel))
                assert review.organization_id == "org_a" and review.status == "pending"
                assert await session.scalar(select(SupplierQuoteModel)) is None
                audit = await session.scalar(select(AuditLogModel).where(AuditLogModel.action_type == "human_review_created"))
                assert audit is not None and audit.organization_id == "org_a"
                snapshot = await session.scalar(select(ProcurementCoordinationStateModel))
                assert snapshot.current_plan["current_step"] == "needs_human"
                assert snapshot.current_plan["plan_id"] == "quote:task_a" and snapshot.version == 4
            with pytest.raises(HTTPException) as repeated:
                await recover()
            assert repeated.value.status_code == 409
        else:
            first = await recover()
            second = await recover()
            if approved:
                assert first.task_status == second.task_status == "completed"
            else:
                assert first.quote_id == second.quote_id
            async with sessions() as session:
                assert len((await session.scalars(select(SupplierQuoteModel))).all()) == 1
                snapshot = await session.scalar(select(ProcurementCoordinationStateModel))
                assert snapshot.current_plan["current_step"] == "completed"
                assert snapshot.current_plan["plan_id"] == "quote:task_a"
                assert snapshot.version == (5 if stage == "completed" else 4)
                assert snapshot.current_plan["orchestration"]["steps"] == []
                assert snapshot.completed_subtask_ids == ["execute_native", "persist_quote"]
    finally:
        if child is not None:
            if child.poll() is None:
                child.kill()
            await asyncio.to_thread(child.communicate, timeout=10)
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


if __name__ == "__main__":
    async def worker():
        engine = _engine(sys.argv[1])
        with pytest.MonkeyPatch.context() as patch:
            _install(engine, patch, sys.argv[2])
            await routes.recover_quote_task("task_a", _user())
        await engine.dispose()
    asyncio.run(worker())
