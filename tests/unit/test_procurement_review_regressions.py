"""Regression checks for the procurement code review (synthetic data only)."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException, Response

from enterprise.approval import routes as approvals
from enterprise.approval.models import ApprovalStatus
from enterprise.procurement import routes
from enterprise.procurement.comparison import compare_quotes
from skyvern.forge.sdk.schemas.tasks import TaskStatus
from tests.unit.test_approval_routes import _install, _user
from tests.unit.test_day_10_quotes import _quote


@pytest.fixture(autouse=True)
def isolate_snapshot_storage(monkeypatch):
    # SQL snapshot/audit atomicity is exercised by test_state01_transactions against PostgreSQL.
    monkeypatch.setattr(routes, "advance_quote_state", AsyncMock())
    monkeypatch.setattr(routes, "write_audit_log", AsyncMock())


def _install_recovery(monkeypatch, state=TaskStatus.created):
    task = SimpleNamespace(
        task_id="task_1", status=state, browser_session_id=None, extracted_information={},
        data_extraction_goal=routes._QUOTE_EXTRACTION_GOAL,
        extracted_information_schema=routes.QUOTE_EXTRACTION_SCHEMA,
        url="https://supplier.example/quote",
    )
    context = SimpleNamespace(organization_id="org_1", department_id="dept_1", category_id="cat_1", risk_level="low")
    database = SimpleNamespace(context=context, approval=None, quote=None, review=None, claimed=False)

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def commit(self):
            pass

        async def scalar(self, statement):
            sql = str(statement)
            if "FROM tasks" in sql:
                return task
            if "supplier_quotes" in sql:
                return database.quote
            if "task_extensions" in sql:
                if "FOR UPDATE" in sql and database.claimed:
                    return None
                return database.context
            if "approval_requests" in sql:
                return database.approval
            if "procurement_human_reviews" in sql:
                return database.review
            return None

    async def update_task(task_id, organization_id, status):
        assert task_id == task.task_id and organization_id == "org_1"
        task.status = status
    database.Session = Session
    database.update_task = AsyncMock(side_effect=update_task)
    monkeypatch.setattr(routes, "forge_app", SimpleNamespace(DATABASE=database))
    monkeypatch.setattr(routes, "_get_smoke_task", AsyncMock(return_value=task))
    monkeypatch.setattr(routes, "write_audit_log", AsyncMock())
    return task, database


@pytest.mark.asyncio
@pytest.mark.parametrize("state", [TaskStatus.running, TaskStatus.queued, TaskStatus.failed, TaskStatus.canceled])
async def test_uncertain_quote_is_never_replayed(monkeypatch, state):
    task, _ = _install_recovery(monkeypatch, state)
    executor = AsyncMock()
    monkeypatch.setattr(routes.AsyncExecutorFactory, "get_executor", staticmethod(lambda: executor))
    review = AsyncMock(return_value=HTTPException(422, "needs_human"))
    monkeypatch.setattr(routes, "_quote_needs_human_confirmation", review)
    with pytest.raises(HTTPException) as error:
        await routes.recover_quote_task(task.task_id, _user("buyer", "operator"))
    assert error.value.status_code == 422
    assert review.await_args.args[1] == "Quote execution was interrupted"
    executor.execute_task.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked", ["claim", "tenant", "viewer", "category", "pending", "rejected", "requester", "missing_approval", "review"])
async def test_quote_recovery_guards(monkeypatch, blocked):
    task, database = _install_recovery(monkeypatch)
    user = _user("buyer", "operator")
    if blocked == "claim":
        database.claimed = True
    elif blocked == "tenant":
        database.context.organization_id = "other"
    elif blocked == "viewer":
        user = _user("buyer", "viewer")
    elif blocked == "category":
        database.context.category_id = "other"
    elif blocked in ("pending", "rejected", "requester"):
        database.approval = SimpleNamespace(
            requester_user_id="other" if blocked == "requester" else "buyer",
            status="approved" if blocked == "requester" else blocked,
        )
    elif blocked == "missing_approval":
        database.context.risk_level = "high"
    else:
        database.review = SimpleNamespace(review_id="review_1", status="terminated")
    with pytest.raises(HTTPException) as error:
        await routes.recover_quote_task(task.task_id, user)
    assert error.value.status_code in (403, 409)
    database.update_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_completed_quote_storage_failure_remains_retryable(monkeypatch):
    task, database = _install_recovery(monkeypatch, TaskStatus.completed)
    quote = SimpleNamespace(quote_id="quote_1")
    persist = AsyncMock(side_effect=[RuntimeError("synthetic DB outage"), quote])
    monkeypatch.setattr(routes, "_persist_extracted_quote", persist)
    with pytest.raises(RuntimeError):
        await routes.recover_quote_task(task.task_id, _user("buyer", "operator"))
    assert await routes.recover_quote_task(task.task_id, _user("buyer", "operator")) is quote
    database.update_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_quote_request_retry_recovers_completed_postprocessing(monkeypatch):
    task, _ = _install_recovery(monkeypatch, TaskStatus.completed)
    user = _user("buyer", "operator")
    payload = routes.QuoteTaskRequest(organization_id="org_1", department_id="dept_1", category_id="cat_1", url=task.url)
    monkeypatch.setattr(routes.settings, "ENV", "local")
    monkeypatch.setattr(routes, "_allowed_smoke_urls", lambda: {task.url})
    monkeypatch.setattr(routes, "_validate_smoke_context", AsyncMock())
    monkeypatch.setattr(routes, "get_procurement_task", AsyncMock())
    monkeypatch.setattr(routes, "_persisted_request", AsyncMock(return_value=(task.task_id, None)))
    persisted = AsyncMock(return_value=SimpleNamespace(quote_id="quote_1", artifact_id="artifact_1"))
    monkeypatch.setattr(routes, "_persist_extracted_quote", persisted)
    result = await routes.quote_task(payload, None, Response(), BackgroundTasks(), "retry", user)
    assert result.idempotent and result.quote_id == "quote_1"
    persisted.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("cross_read", [False, True])
async def test_read_scope_does_not_grant_procurement_write(monkeypatch, cross_read):
    user = _user("buyer", "operator", department_id="dept_a")
    user.has_cross_org_read = cross_read
    if not cross_read:
        user.department_roles.append(user.department_roles[0].model_copy(update={
            "department_id": "dept_b", "role": "viewer",
        }))
    session = AsyncMock()
    session.scalar.return_value = SimpleNamespace()
    session.__aenter__.return_value = session
    monkeypatch.setattr(routes, "forge_app", SimpleNamespace(DATABASE=SimpleNamespace(Session=lambda: session)))
    payload = SimpleNamespace(department_id="dept_b", category_id="cat_1", task_id="task_b", artifact_id="artifact_b", organization_id=user.org_id)
    for validate in (
        lambda: routes._validate_quote_context(session, payload, user),
        lambda: routes._validate_smoke_context(payload, user),
    ):
        with pytest.raises(HTTPException) as denied:
            await validate()
        assert denied.value.status_code == 403
    session.scalar.assert_not_awaited()


def test_mixed_materials_cannot_produce_a_recommendation():
    ssd = _quote("ssd", "org", "supplier_a", "100")
    paper = _quote("paper", "org", "supplier_b", "1")
    paper.material_name = "Paper"
    with pytest.raises(ValueError):
        compare_quotes(iter([ssd, paper]))
    with pytest.raises(HTTPException) as invalid:
        routes._comparison_response([ssd, paper])
    assert invalid.value.status_code == 422


@pytest.mark.asyncio
async def test_approved_quote_runs_and_persists_before_response(monkeypatch):
    database = _install(monkeypatch)
    approval = database.approvals["apr_1"]
    approval.status = "approved"
    approval.approver_user_id = "approver"
    task = database.tasks["task_1"]
    task.data_extraction_goal = routes._QUOTE_EXTRACTION_GOAL
    task.extracted_information_schema = routes.QUOTE_EXTRACTION_SCHEMA
    task.url = "https://supplier.example/quote"
    original_session = database.Session
    def session_factory():
        session = original_session()
        original_scalar = session.scalar
        async def scalar(statement):
            if "supplier_quotes" in str(statement):
                return None
            if "task_extensions" in str(statement):
                return SimpleNamespace(organization_id="org_1", department_id="dept_1", category_id="cat_1", risk_level="low")
            return await original_scalar(statement)
        session.scalar = scalar
        return session
    database.Session = session_factory
    monkeypatch.setattr(routes, "forge_app", SimpleNamespace(DATABASE=database))
    events = []
    async def execute():
        events.append("execute")
        task.status = TaskStatus.completed
    class Executor:
        async def execute_task(self, **kwargs):
            kwargs["background_tasks"].add_task(execute)
    async def persist(completed, payload, user):
        assert completed.status == TaskStatus.completed
        assert payload.department_id == "dept_1"
        assert user.user_id == "buyer_1"
        events.append("persist")
    monkeypatch.setattr(approvals.AsyncExecutorFactory, "get_executor", staticmethod(lambda: Executor()))
    monkeypatch.setattr(routes, "_persist_extracted_quote", persist)
    monkeypatch.setattr(routes, "_get_smoke_task", AsyncMock(return_value=task))
    background = BackgroundTasks()
    result = await approvals.continue_request("apr_1", background, _user("buyer_1", "operator"))
    assert events == ["execute", "persist"]
    assert result.task_status == TaskStatus.completed.value


@pytest.mark.asyncio
async def test_completed_approved_quote_can_be_recovered_without_reexecution(monkeypatch):
    database = _install(monkeypatch)
    approval = database.approvals["apr_1"]
    approval.status = ApprovalStatus.APPROVED.value
    task = database.tasks["task_1"]
    task.status = TaskStatus.completed
    task.data_extraction_goal = routes._QUOTE_EXTRACTION_GOAL
    task.extracted_information_schema = routes.QUOTE_EXTRACTION_SCHEMA
    task.url = "https://supplier.example/quote"
    original_session = database.Session

    def session_factory():
        session = original_session()
        original_scalar = session.scalar

        async def scalar(statement):
            if "supplier_quotes" in str(statement):
                return None
            if "task_extensions" in str(statement):
                return SimpleNamespace(organization_id="org_1", department_id="dept_1", category_id="cat_1", risk_level="low")
            return await original_scalar(statement)

        session.scalar = scalar
        return session

    database.Session = session_factory
    monkeypatch.setattr(routes, "forge_app", SimpleNamespace(DATABASE=database))
    persisted = AsyncMock()
    monkeypatch.setattr(routes, "_persist_extracted_quote", persisted)
    monkeypatch.setattr(routes, "_get_smoke_task", AsyncMock(return_value=task))
    executor = AsyncMock()
    monkeypatch.setattr(approvals.AsyncExecutorFactory, "get_executor", staticmethod(lambda: executor))

    result = await approvals.continue_request("apr_1", BackgroundTasks(), _user("buyer_1", "operator"))

    assert result.task_status == TaskStatus.completed.value
    executor.execute_task.assert_not_awaited()
    persisted.assert_awaited_once()


@pytest.mark.parametrize("role,org,department,category,allowed", [
    ("operator", "org_1", "dept_1", "cat_1", True),
    ("operator", "org_other", "dept_1", "cat_1", False),
    ("operator", "org_1", "dept_other", "cat_1", False),
    ("operator", "org_1", "dept_1", "cat_other", False),
    ("org_admin", "org_1", "dept_other", "cat_other", True),
    ("org_admin", "org_other", "dept_1", "cat_1", False),
])
def test_write_scope_boundaries(role, org, department, category, allowed):
    user = _user("buyer", role)
    if allowed:
        routes._assert_procurement_operator(user, org, department, category)
    else:
        with pytest.raises(HTTPException) as denied:
            routes._assert_procurement_operator(user, org, department, category)
        assert denied.value.status_code == 403


@pytest.mark.parametrize("field,value", [
    ("quantity", Decimal("20")), ("unit", "box"), ("currency", "USD"),
])
def test_comparison_requires_matching_purchase_terms(field, value):
    a = _quote("a", "org", "supplier_a", "100")
    b = _quote("b", "org", "supplier_b", "90")
    setattr(b, field, value)
    with pytest.raises(ValueError):
        compare_quotes([a, b])


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["execution", "incomplete", "validation"])
async def test_approved_quote_failure_creates_human_review(monkeypatch, failure):
    task, database = _install_recovery(monkeypatch)
    async def execute():
        if failure == "execution":
            raise RuntimeError("synthetic execution failure")
        task.status = TaskStatus.failed if failure == "incomplete" else TaskStatus.completed
    class Executor:
        async def execute_task(self, **kwargs):
            kwargs["background_tasks"].add_task(execute)
    monkeypatch.setattr(routes.AsyncExecutorFactory, "get_executor", staticmethod(lambda: Executor()))
    review = AsyncMock(return_value=HTTPException(status_code=422, detail={"code": "quote_needs_human_confirmation"}))
    monkeypatch.setattr(routes, "_quote_needs_human_confirmation", review)
    with pytest.raises(HTTPException) as error:
        await routes.recover_quote_task(task.task_id, _user("buyer", "operator"))
    assert error.value.status_code == 422
    review.assert_awaited_once()


@pytest.mark.asyncio
async def test_approved_quote_replay_reads_persisted_quote(monkeypatch):
    user = _user("buyer", "operator")
    payload = routes.QuoteTaskRequest(organization_id=user.org_id, department_id="dept_1", category_id="cat_1", url="https://supplier.example/quote")
    monkeypatch.setattr(routes.settings, "ENV", "local")
    monkeypatch.setattr(routes, "_allowed_smoke_urls", lambda: {payload.url})
    monkeypatch.setattr(routes, "_validate_smoke_context", AsyncMock())
    monkeypatch.setattr(routes, "_persisted_request", AsyncMock(return_value=("task_1", "apr_1")))
    scoped_task = AsyncMock()
    monkeypatch.setattr(routes, "get_procurement_task", scoped_task)
    monkeypatch.setattr(routes, "_get_smoke_task", AsyncMock(return_value=SimpleNamespace(task_id="task_1", status=TaskStatus.completed)))
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.scalar.return_value = SimpleNamespace(quote_id="quote_1", artifact_id="artifact_1")
    monkeypatch.setattr(routes, "forge_app", SimpleNamespace(DATABASE=SimpleNamespace(Session=lambda: session)))
    result = await routes.quote_task(payload, None, Response(), BackgroundTasks(), "retry", user)
    assert result.idempotent and result.quote_id == "quote_1" and result.artifact_id == "artifact_1"
    scoped_task.assert_awaited_once_with("task_1", user)
