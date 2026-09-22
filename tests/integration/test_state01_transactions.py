"""Opt-in disposable PostgreSQL checks for quote state and business/audit atomicity."""

import json
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, event, select, text, update

from enterprise.approval import routes as approvals
from enterprise.approval.models import ApprovalRequestModel
from enterprise.audit.models import AuditLogModel
from enterprise.auth.models import EnterpriseUserModel, TaskExtensionModel
from enterprise.llm.human_intervention import ResolutionAction
from enterprise.procurement import routes
from enterprise.procurement.models import ProcurementCoordinationStateModel as State
from enterprise.procurement.models import ProcurementHumanReviewModel, SupplierQuoteModel
from enterprise.procurement.quote_state import advance_quote_state, load_quote_state, quote_state_response
from skyvern.forge.sdk.db.models import TaskModel
from tests.integration.test_run01_recovery import _engine, _install, _seed
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
        yield engine, _install(engine, monkeypatch)
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


async def advance(session, step, **kwargs):
    return await advance_quote_state(
        session, task_id="task_a", org_id="org_a", department_id="dept_a",
        executor="user_a", step=step, **kwargs,
    )


def fail_write(engine, table):
    def fail(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.startswith((f"INSERT INTO {table}", f"UPDATE {table}")):
            raise RuntimeError("synthetic transaction failure")
    event.listen(engine.sync_engine, "before_cursor_execute", fail)
    return fail


async def test_snapshot_restart_stale_version_and_safe_response(database):
    engine, sessions = database
    async with sessions() as session:
        assert await advance(session, "ready", expected_version=0) == 1
        await session.commit()
    await engine.dispose()  # No live connection or in-memory state needed to reload.
    async with sessions() as first, sessions() as stale, sessions() as unchanged:
        old = await load_quote_state(stale, "task_a", "org_a")
        unchanged_old = await load_quote_state(unchanged, "task_a", "org_a")
        before = quote_state_response(old)
        assert before == dict(task_id="task_a", template_id="quote-task/v1", plan_id="quote:task_a",
                              current_step="ready", input_ref="task_a", version=1)
        assert await load_quote_state(first, "task_a", "another_org") is None
        await advance(first, "running", expected_version=1)
        await first.commit()
        with pytest.raises(HTTPException) as conflict:
            await advance(stale, "completed", expected_version=1)
        assert conflict.value.status_code == 409
        await stale.rollback()
        with pytest.raises(HTTPException) as conflict:
            await advance(unchanged, "ready", expected_version=unchanged_old.version)
        assert conflict.value.status_code == 409
        await unchanged.rollback()
    with pytest.raises(HTTPException) as conflict:
        await routes.recover_quote_task("task_a", _user(), expected_version=1)
    assert conflict.value.status_code == 409
    async with sessions() as session:
        state = quote_state_response(await load_quote_state(session, "task_a", "org_a"))
        assert state["version"] == 2 and state["plan_id"] == before["plan_id"]
        events = (await session.scalars(select(AuditLogModel))).all()
        assert [json.loads(item.input_value)["version"] for item in events] == [1, 2]
    from enterprise.agent.coordinator import AgentCoordinator, CoordinationStateConflict
    coordinator = AgentCoordinator(None, None, session_factory=sessions)
    with pytest.raises(CoordinationStateConflict):
        await coordinator._load_state("task_a", "org_a")
    response = await routes.get_quote_state("task_a", _user())
    assert response["state"] == state
    outsider = _user().model_copy(update={"org_id": "another_org"})
    with pytest.raises(HTTPException) as denied:
        await routes.get_quote_state("task_a", outsider)
    assert denied.value.status_code == 404


@pytest.mark.parametrize("table", ["audit_logs", "procurement_coordination_states", "supplier_quotes"])
async def test_quote_business_state_and_audit_roll_back_together(database, table):
    engine, sessions = database
    async with sessions() as session:
        await session.execute(update(TaskModel).values(status="completed"))
        await session.commit()
    fault = fail_write(engine, table)
    try:
        with pytest.raises(RuntimeError, match="synthetic transaction failure"):
            await routes.recover_quote_task("task_a", _user())
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fault)
    async with sessions() as session:
        for model in (State, SupplierQuoteModel, AuditLogModel):
            assert await session.scalar(select(model)) is None
    result = await routes.recover_quote_task("task_a", _user())
    assert result.task_id == "task_a"
    async with sessions() as session:
        state = await load_quote_state(session, "task_a", "org_a")
        assert state.current_plan["current_step"] == "completed"
        assert await session.scalar(select(AuditLogModel)) is not None


async def test_running_audit_failure_prevents_native_execution(database, monkeypatch):
    engine, sessions = database
    from unittest.mock import AsyncMock
    executor = AsyncMock()
    monkeypatch.setattr(routes.AsyncExecutorFactory, "get_executor", staticmethod(lambda: executor))
    fault = fail_write(engine, "audit_logs")
    try:
        with pytest.raises(RuntimeError):
            await routes.recover_quote_task("task_a", _user())
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fault)
    executor.execute_task.assert_not_awaited()
    async with sessions() as session:
        assert (await session.scalar(select(TaskModel))).status == "created"
        assert await session.scalar(select(State)) is None
        assert await session.scalar(select(AuditLogModel)) is None


async def test_initial_context_and_approval_roll_back_with_audit(database):
    engine, sessions = database
    async with sessions() as session:
        await session.execute(delete(TaskExtensionModel))
        await session.commit()
    payload = _payload()
    payload.risk = routes.ProcurementRiskInput(total_amount_cny="1000000")
    risk = await routes.detect_risk(payload.risk.to_context())
    assert risk.risk_level in ("high", "critical")
    fault = fail_write(engine, "audit_logs")
    try:
        with pytest.raises(RuntimeError):
            await routes._attach_procurement_context("task_a", payload, _user(), risk)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fault)
    async with sessions() as session:
        for model in (TaskExtensionModel, ApprovalRequestModel, State, AuditLogModel):
            assert await session.scalar(select(model)) is None
    approval_id = await routes._attach_procurement_context("task_a", payload, _user(), risk)
    approver = _user().model_copy(update={"user_id": "approver_a"})
    approver.department_roles = [approver.department_roles[0].model_copy(update={"role": "approver"})]
    async with sessions() as session:
        session.add(EnterpriseUserModel(user_id="approver_a", organization_id="org_a", username="approver",
                                        password_hash="not-a-login", display_name="Synthetic Approver"))
        await session.commit()
    fault = fail_write(engine, "audit_logs")
    try:
        with pytest.raises(RuntimeError):
            await approvals.reject_request(approval_id, approvals.DecisionRequest(), approver)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fault)
    async with sessions() as session:
        assert (await session.scalar(select(ApprovalRequestModel))).status == "pending"
        assert (await session.scalar(select(TaskModel))).status == "created"
        assert (await session.scalar(select(State))).current_plan["current_step"] == "awaiting_approval"
    await approvals.reject_request(approval_id, approvals.DecisionRequest(), approver)
    async with sessions() as session:
        assert (await session.scalar(select(TaskModel))).status == "canceled"
        assert (await session.scalar(select(State))).current_plan["current_step"] == "rejected"


async def test_human_review_and_resolution_are_atomic(database):
    engine, sessions = database
    fault = fail_write(engine, "audit_logs")
    try:
        with pytest.raises(RuntimeError):
            await routes._create_or_get_quote_human_review(
                "task_a", _payload(), _user(), reason_code="quote_execution_interrupted",
                safe_error_summary="Quote execution was interrupted",
            )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fault)
    async with sessions() as session:
        assert await session.scalar(select(ProcurementHumanReviewModel)) is None
        assert await session.scalar(select(State)) is None
    review = await routes._create_or_get_quote_human_review(
        "task_a", _payload(), _user(), reason_code="quote_execution_interrupted",
        safe_error_summary="Quote execution was interrupted",
    )
    fault = fail_write(engine, "audit_logs")
    body = routes.HumanReviewResolutionRequest(action=ResolutionAction.TERMINATE)
    try:
        with pytest.raises(RuntimeError):
            await routes.resolve_human_review(review.review_id, body, _user())
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fault)
    async with sessions() as session:
        assert (await session.scalar(select(ProcurementHumanReviewModel))).status == "pending"
        assert (await session.scalar(select(State))).current_plan["current_step"] == "needs_human"
        assert (await session.scalar(select(TaskModel))).status == "created"
    await routes.resolve_human_review(review.review_id, body, _user())
    async with sessions() as session:
        assert (await session.scalar(select(State))).current_plan["current_step"] == "terminated"
