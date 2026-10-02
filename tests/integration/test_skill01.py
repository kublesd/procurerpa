"""Disposable PostgreSQL native quote template and Skill evidence checks."""
import json
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, event, select, update

from enterprise.approval.models import ApprovalRequestModel
from enterprise.audit.models import AuditLogModel
from enterprise.auth.dependencies import get_current_user
from enterprise.auth.models import TaskExtensionModel
from enterprise.procurement import routes as procurement
from enterprise.procurement.models import ProcurementCoordinationStateModel as State
from enterprise.procurement.models import ProcurementHumanReviewModel, SupplierQuoteModel
from enterprise.workflows import routes as workflows
from skyvern.forge.sdk.db.models import TaskModel
from tests.integration import test_approval01
from tests.integration.test_state01_transactions import database as database
from tests.integration.test_state01_transactions import pytestmark as pytestmark
from tests.unit.test_day_11_quotes import _payload, _user

approval_database = test_approval01.database


async def test_template_runs_native_quote_once_and_reloads_skill_evidence(database, monkeypatch):
    engine, sessions = database
    async with sessions() as session:
        await session.execute(delete(TaskExtensionModel))
        await session.commit()
    monkeypatch.setattr(procurement.settings, "ENV", "local")
    monkeypatch.setattr(procurement.settings, "PROCUREMENT_SMOKE_ALLOWED_URLS", _payload().url)
    creator = AsyncMock(return_value=await procurement._get_smoke_task("task_a", "org_a"))
    monkeypatch.setattr(procurement, "_create_smoke_task", creator)
    executor = procurement.AsyncExecutorFactory.get_executor()
    execute = AsyncMock(wraps=executor.execute_task)
    executor.execute_task = execute
    monkeypatch.setattr(procurement.AsyncExecutorFactory, "get_executor", staticmethod(lambda: executor))
    payload = _payload()
    payload.risk = procurement.ProcurementRiskInput(
        supplier_id="synthetic", supplier_qualified=True, selected_quote_cny="10", average_quote_cny="10",
    )
    app = FastAPI()
    app.include_router(workflows.router)
    app.include_router(procurement.router)
    app.dependency_overrides[get_current_user] = _user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for attempt in range(2):
            response = await client.post(
                "/enterprise/workflows/instantiate/quote-task/v1", json=payload.model_dump(mode="json"),
                headers={"Idempotency-Key": "synthetic-skill01"},
            )
            assert response.status_code == 200, response.text
            assert response.json()["idempotent"] == bool(attempt)
            assert response.json()["artifact_id"] == "artifact_a"
            assert response.json()["template_id"] == "quote-task/v1"
            await engine.dispose()
        state_response = await client.get("/enterprise/procurement/tasks/task_a/quote-state")
        assert state_response.status_code == 200
        assert state_response.json()["state"]["skills"] == [{
            "step_id": "table_extract:0", "skill_name": "table_extract", "task_id": "task_a",
            "status": "completed", "artifact_id": "artifact_a",
        }]
    creator.assert_awaited_once()
    execute.assert_awaited_once()
    assert creator.await_args.kwargs["task_request"].extracted_information_schema == procurement.QUOTE_EXTRACTION_SCHEMA
    async with sessions() as session:
        assert len((await session.scalars(select(SupplierQuoteModel))).all()) == 1
        events = (await session.scalars(select(AuditLogModel).where(
            AuditLogModel.action_type == "skill_state_changed",
        ).order_by(AuditLogModel.action_index))).all()
        assert [event.execution_result for event in events] == ["pending", "running", "completed"]
        assert json.loads(events[-1].input_value)["artifact_id"] == "artifact_a"
        assert "https://" not in "".join(event.input_value for event in events)


async def test_skill_audit_failure_rolls_back_quote_and_completion(database):
    engine, sessions = database
    async with sessions() as session:
        await session.execute(update(TaskModel).values(status="completed"))
        await procurement.save_quote_plan(
            session, task_id="task_a", org_id="org_a", department_id="dept_a", executor="user_a",
            plan={"steps": ["persist_quote"], "completed": ["execute_native"], "source": "llm"},
        )
        await session.commit()
    def fail_skill(_connection, _cursor, _sql, _params, context, _many):
        if any(
            row.get("action_type") == "skill_state_changed" and row.get("execution_result") == "completed"
            for row in context.compiled_parameters or []
        ):
            raise RuntimeError("synthetic Skill audit failure")
    event.listen(engine.sync_engine, "before_cursor_execute", fail_skill)
    try:
        with pytest.raises(RuntimeError, match="synthetic Skill audit failure"):
            await procurement.recover_quote_task("task_a", _user())
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fail_skill)
    async with sessions() as session:
        assert await session.scalar(select(SupplierQuoteModel)) is None
        state = await session.scalar(select(State))
        assert state.current_plan["skills"][0]["status"] == "pending"
        assert state.current_plan["current_step"] == "ready"
    await procurement.recover_quote_task("task_a", _user())


@pytest.mark.parametrize("native_status", ["running", "completed"])
async def test_human_quote_does_not_claim_successful_skill_extraction(database, native_status):
    _, sessions = database
    async with sessions() as session:
        await session.execute(update(TaskModel).values(status=native_status))
        await session.commit()
    await procurement._create_or_get_quote_human_review(
        "task_a", _payload(), _user(), reason_code="quote_schema_invalid", safe_error_summary="synthetic",
        artifact_id="artifact_a",
    )
    async with sessions() as session:
        review_id = await session.scalar(select(ProcurementHumanReviewModel.review_id))
        state = await session.scalar(select(State))
        assert state.current_plan["skills"][0]["status"] == "needs_human"
        assert state.current_plan["skills"][0]["artifact_id"] == "artifact_a"
    await procurement.resolve_human_review(
        review_id, procurement.HumanReviewResolutionRequest(
            action="manual_complete", manual_result={
                "supplier_id": "synthetic", "material_name": "SSD", "quantity": "10", "unit": "unit",
                "currency": "CNY", "unit_price_cny": "10", "freight_cny": "0", "moq": "1",
                "delivery_days": 5, "artifact_id": "artifact_a",
            },
        ), _user(),
    )
    async with sessions() as session:
        state = await session.scalar(select(State))
        assert state.current_plan["skills"][0]["status"] == "manual_completed"
        assert state.current_plan["skills"][0]["artifact_id"] == "artifact_a"


async def test_native_template_waits_for_real_approval_without_browser_execution(approval_database, monkeypatch):
    engine, sessions = approval_database
    payload = _payload()
    payload.risk = procurement.ProcurementRiskInput(total_amount_cny="100000")
    monkeypatch.setattr(procurement.settings, "ENV", "local")
    monkeypatch.setattr(procurement, "_allowed_smoke_urls", lambda: {payload.url})
    monkeypatch.setattr(procurement, "review_risk", AsyncMock(return_value={"risk_level": "high"}))
    monkeypatch.setattr(procurement, "_schedule_approval_notification", Mock())
    monkeypatch.setattr(procurement, "_create_smoke_task", AsyncMock(
        return_value=await procurement._get_smoke_task("task_a", "org_a"),
    ))
    executor = AsyncMock()
    monkeypatch.setattr(procurement.AsyncExecutorFactory, "get_executor", staticmethod(lambda: executor))
    app = FastAPI()
    app.include_router(workflows.router)
    app.dependency_overrides[get_current_user] = _user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/enterprise/workflows/instantiate/quote-task/v1", json=payload.model_dump(mode="json"),
            headers={"Idempotency-Key": "synthetic-approval-skill"},
        )
    assert response.status_code == 202, response.text
    assert response.json()["outcome"] == "pending_approval"
    executor.execute_task.assert_not_awaited()
    await engine.dispose()
    async with sessions() as session:
        approval = await session.get(ApprovalRequestModel, response.json()["approval_id"])
        assert approval.status == "pending" and approval.approver_department_id == "dept_a"
        state = await session.scalar(select(State))
        assert state.current_plan["skills"][0]["status"] == "blocked"
        assert await session.scalar(select(SupplierQuoteModel)) is None
        assert (await session.get(TaskModel, "task_a")).status == "created"


async def test_manual_quote_api_does_not_claim_native_extraction(database):
    _, sessions = database
    async with sessions() as session:
        await session.execute(update(TaskModel).values(status="completed"))
        await session.commit()
    await procurement.create_supplier_quote(procurement.QuoteCreateRequest(
        task_id="task_a", department_id="dept_a", category_id="pc_a",
        supplier_id="synthetic", material_name="SSD", quantity="10", unit="unit", currency="CNY",
        unit_price_cny="10", freight_cny="0", moq="1", delivery_days=5, artifact_id="artifact_a",
    ), _user())
    async with sessions() as session:
        state = await session.scalar(select(State))
        assert state.current_plan["skills"][0]["status"] == "manual_completed"
        assert state.current_plan["skills"][0]["artifact_id"] == "artifact_a"
