"""Disposable local PostgreSQL/Redis acceptance checks; synthetic data only."""

import asyncio
import datetime
import importlib.util
import json
import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import BackgroundTasks, HTTPException
from redis.asyncio import Redis
from sqlalchemy import delete, event, inspect, select, text

from enterprise.approval import notifications
from enterprise.approval import routes as approvals
from enterprise.approval.models import ApprovalRequestModel
from enterprise.approval.policy import POLICY_VERSION
from enterprise.approval.risk_detector import detect_risk
from enterprise.auth import dependencies
from enterprise.auth.models import DepartmentModel, EnterpriseUserModel, TaskExtensionModel, UserDepartmentRoleModel
from enterprise.auth.schemas import DepartmentRole
from enterprise.procurement import routes
from enterprise.procurement.models import SupplierQuoteModel, UserProcurementCategoryModel
from skyvern.forge.sdk.db.models import Base, OrganizationModel, TaskModel
from tests.integration.test_run01_recovery import _engine, _install, _seed
from tests.integration.test_state01_transactions import fail_write
from tests.unit.test_day_11_quotes import _payload, _user

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(
    not os.environ.get("RUN01_TEST_DATABASE_URL"), reason="Requires disposable localhost PostgreSQL",
)]


@pytest_asyncio.fixture
async def database(monkeypatch):
    schema = "run01_test_" + uuid4().hex
    engine = _engine(schema)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await _seed(engine, False)
        async with engine.begin() as connection:
            await connection.run_sync(lambda conn: Base.metadata.create_all(conn, tables=[
                UserDepartmentRoleModel.__table__, UserProcurementCategoryModel.__table__,
                dependencies.UserBusinessLineModel.__table__, dependencies.SpecialPermissionModel.__table__,
            ]))
        sessions = _install(engine, monkeypatch)
        monkeypatch.setattr(dependencies, "forge_app", routes.forge_app)
        async with sessions() as session:
            await session.execute(delete(TaskExtensionModel))
            session.add(OrganizationModel(organization_id="org_b", organization_name="Synthetic other"))
            await session.flush()
            session.add_all([
                DepartmentModel(department_id="compliance", organization_id="org_a",
                                department_name="Synthetic compliance", department_code="COMPLIANCE"),
                DepartmentModel(department_id="other_compliance", organization_id="org_b",
                                department_name="Synthetic other compliance", department_code="COMPLIANCE"),
                EnterpriseUserModel(user_id="approver", organization_id="org_a", username="test_approver",
                                    password_hash="not-a-login", display_name="Synthetic approver"),
            ])
            await session.flush()
            session.add_all([
                UserDepartmentRoleModel(user_id="approver", department_id="dept_a", role="approver"),
                UserDepartmentRoleModel(user_id="approver", department_id="compliance", role="approver"),
                UserDepartmentRoleModel(user_id="user_a", department_id="dept_a", role="operator"),
                UserProcurementCategoryModel(user_id="approver", category_id="pc_a"),
                UserProcurementCategoryModel(user_id="user_a", category_id="pc_a"),
            ])
            await session.commit()
        yield engine, sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


async def attach(amount="100000"):
    payload = _payload()
    payload.risk.total_amount_cny = Decimal(amount)
    risk = await detect_risk(payload.risk.to_context())
    return await routes._attach_procurement_context("task_a", payload, _user(), risk)


def approver():
    return _user().model_copy(update={"user_id": "approver", "department_roles": [
        DepartmentRole(department_id=dept, department_name="Synthetic", role="approver")
        for dept in ("dept_a", "compliance")
    ]})


@pytest.mark.parametrize("amount,department", [("100000", "dept_a"), ("1000000", "compliance")])
async def test_creation_snapshot_and_restart(database, amount, department):
    engine, sessions = database
    approval_id = await attach(amount)
    await engine.dispose()
    async with sessions() as session:
        approval = await session.get(ApprovalRequestModel, approval_id)
        assert approval.approver_department_id == department
        assert approval.category_id == "pc_a" and approval.policy_version == POLICY_VERSION
        assert approval.total_amount_cny == Decimal(amount)
        assert approval.matched_threshold_cny == approval.total_amount_cny
        assert approval.policy_effective_at.isoformat() == "2026-09-22T00:00:00+00:00"
    assert len(await approvals.list_pending_approvals(approver())) == 1
    assert await approvals.list_pending_approvals(_user()) == []


@pytest.mark.parametrize("failure", ["missing", "category", "inactive", "cross_org", "self"])
async def test_database_route_failure_rolls_back_context(database, failure):
    _, sessions = database
    async with sessions() as session:
        if failure == "missing":
            dept = await session.get(DepartmentModel, "compliance")
            dept.deleted_at = datetime.datetime.now()
        elif failure == "category":
            await session.execute(delete(UserProcurementCategoryModel).where(
                UserProcurementCategoryModel.user_id == "approver"))
        elif failure == "inactive":
            (await session.get(EnterpriseUserModel, "approver")).is_active = False
        elif failure == "cross_org":
            (await session.get(EnterpriseUserModel, "approver")).organization_id = "org_b"
        else:
            await session.execute(delete(UserDepartmentRoleModel).where(UserDepartmentRoleModel.user_id == "approver"))
            session.add(UserDepartmentRoleModel(user_id="user_a", department_id="compliance", role="approver"))
        await session.commit()
    with pytest.raises(HTTPException) as denied:
        await attach("1000000")
    assert denied.value.status_code == 422
    async with sessions() as session:
        assert await session.scalar(select(ApprovalRequestModel)) is None
        assert await session.scalar(select(TaskExtensionModel)) is None


@pytest.mark.parametrize("decision", ["approved", "rejected"])
async def test_decision_commits_before_publish_and_duplicate_is_rejected(database, monkeypatch, decision):
    _, sessions = database
    approval_id = await attach()
    seen = []

    async def publish(org_id, identifier, status, actor_id):
        async with sessions() as session:
            stored = await session.get(ApprovalRequestModel, identifier)
            task = await session.get(TaskModel, "task_a")
            assert stored.status == status == decision
            assert task.status == ("canceled" if decision == "rejected" else "created")
        seen.append((org_id, identifier, status, actor_id))

    monkeypatch.setattr(approvals, "publish_update", publish)
    action = approvals.approve_request if decision == "approved" else approvals.reject_request
    await action(approval_id, approvals.DecisionRequest(), approver())
    with pytest.raises(HTTPException) as conflict:
        await action(approval_id, approvals.DecisionRequest(), approver())
    assert conflict.value.status_code == 409 and len(seen) == 1


async def test_subscription_authorization_and_database_recheck(database, monkeypatch):
    approval_id = await attach()
    calls = []

    async def wakeup(*args):
        calls.append(args)
        await approvals.approve_request(approval_id, approvals.DecisionRequest(), approver())

    monkeypatch.setattr(approvals, "wait_for_update", wakeup)
    outsider = _user().model_copy(update={"org_id": "org_b"})
    with pytest.raises(HTTPException):
        await approvals.approval_updates(approval_id, 1, outsider)
    assert not calls
    result = await approvals.approval_updates(approval_id, 1, _user())
    assert result.status == "approved" and calls
    async with database[1]() as session:
        assert (await session.get(TaskModel, "task_a")).status == "created"


async def test_forged_or_lost_notice_does_not_decide(database, monkeypatch):
    approval_id = await attach()
    async def no_event(*args):
        return None
    monkeypatch.setattr(approvals, "wait_for_update", no_event)
    result = await approvals.approval_updates(approval_id, 1, _user())
    assert result.status == "pending"


async def test_concurrent_decisions_only_one_commits(database):
    approval_id = await attach()
    results = await asyncio.gather(
        approvals.approve_request(approval_id, approvals.DecisionRequest(), approver()),
        approvals.reject_request(approval_id, approvals.DecisionRequest(), approver()),
        return_exceptions=True,
    )
    assert sum(isinstance(result, HTTPException) and result.status_code == 409 for result in results) == 1
    assert sum(isinstance(result, approvals.DecisionResponse) for result in results) == 1


async def test_rollback_does_not_publish(database, monkeypatch):
    engine, sessions = database
    approval_id = await attach()
    publish = AsyncMock()
    monkeypatch.setattr(approvals, "publish_update", publish)
    fault = fail_write(engine, "audit_logs")
    try:
        with pytest.raises(RuntimeError):
            await approvals.approve_request(approval_id, approvals.DecisionRequest(), approver())
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fault)
    publish.assert_not_awaited()
    async with sessions() as session:
        assert (await session.get(ApprovalRequestModel, approval_id)).status == "pending"


async def test_concurrent_continue_executes_once(database, monkeypatch):
    _, sessions = database
    approval_id = await attach()
    await approvals.approve_request(approval_id, approvals.DecisionRequest(), approver())
    started, finish = asyncio.Event(), asyncio.Event()
    calls = []

    async def execute(**kwargs):
        calls.append(kwargs["task_id"])
        started.set()
        await finish.wait()
        async with sessions() as session:
            (await session.get(TaskModel, "task_a")).status = "completed"
            await session.commit()

    executor = AsyncMock()
    executor.execute_task.side_effect = execute
    monkeypatch.setattr(routes.AsyncExecutorFactory, "get_executor", staticmethod(lambda: executor))
    first = asyncio.create_task(approvals.continue_request(approval_id, BackgroundTasks(), _user()))
    try:
        await asyncio.wait_for(started.wait(), 15)
        with pytest.raises(HTTPException) as conflict:
            await approvals.continue_request(approval_id, BackgroundTasks(), _user())
        assert conflict.value.status_code == 409
    finally:
        finish.set()
        await asyncio.wait_for(first, 15)
    assert calls == ["task_a"]
    async with sessions() as session:
        assert len((await session.scalars(select(SupplierQuoteModel))).all()) == 1


async def test_redis_safe_payload_isolation_and_outage(database, monkeypatch):
    client = Redis.from_url("redis://127.0.0.1:56379/0")
    monkeypatch.setattr(notifications, "redis_client", lambda: Redis.from_url("redis://127.0.0.1:56379/0"))
    approval_id = await attach()
    async with client.pubsub() as subscriber:
        await subscriber.subscribe(notifications.channel_name("org_a", approval_id))
        await subscriber.get_message(timeout=1)
        await notifications.publish_update("org_b", approval_id, "approved", "approver")
        assert await subscriber.get_message(ignore_subscribe_messages=True, timeout=0.1) is None
        watching = asyncio.create_task(approvals.approval_updates(approval_id, 10, _user()))
        for _ in range(100):
            counts = await client.pubsub_numsub(notifications.channel_name("org_a", approval_id))
            if counts[0][1] == 2:
                break
            await asyncio.sleep(0.05)
        assert counts[0][1] == 2
        await approvals.approve_request(approval_id, approvals.DecisionRequest(note="never in event"), approver())
        assert (await asyncio.wait_for(watching, 10)).status == "approved"
        message = await subscriber.get_message(ignore_subscribe_messages=True, timeout=1)
        assert json.loads(message["data"]) == dict(approval_id=approval_id, status="approved", actor_id="approver")
    await client.aclose()
    monkeypatch.setattr(notifications, "redis_client", lambda: Redis.from_url(
        "redis://127.0.0.1:1/0", socket_connect_timeout=0.1))
    await notifications.publish_update("org_a", approval_id, "approved", "approver")
    await notifications.wait_for_update("org_a", approval_id, 1)
    assert (await approvals.get_approval(approval_id, _user())).status == "approved"


async def test_migration_upgrade_downgrade_preserves_legacy(database):
    engine, _ = database
    path = Path("alembic/versions/2026_09_22_0012_approval_policy.py")
    spec = importlib.util.spec_from_file_location("approval_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def exercise(connection):
        # Only this disposable fixture schema is changed.
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            # Model-created FK is unnamed by the migration; use its actual database name.
            fk = next(key for key in inspect(connection).get_foreign_keys("approval_requests")
                      if key["constrained_columns"] == ["category_id"])
            connection.execute(text(f'ALTER TABLE approval_requests RENAME CONSTRAINT "{fk["name"]}" TO fk_approval_category'))
            migration.downgrade()
            connection.execute(text("INSERT INTO approval_requests "
                "(approval_id,task_id,organization_id,department_id,requester_user_id,risk_level,risk_reason,"
                "approver_department_id,approver_role,status,requested_at,timeout_seconds) VALUES "
                "('legacy','task_a','org_a','dept_a','user_a','high','synthetic','dept_a','approver','pending',now(),3600)"))
            migration.upgrade()
            assert connection.execute(text("SELECT policy_version FROM approval_requests WHERE approval_id='legacy'")).scalar() is None
            migration.downgrade()
            assert "policy_version" not in {column["name"] for column in inspect(connection).get_columns("approval_requests")}
            migration.upgrade()
    async with engine.begin() as connection:
        await connection.run_sync(exercise)
