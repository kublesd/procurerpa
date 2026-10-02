"""Real quote entry and durable risk audit; disposable PostgreSQL, synthetic model."""

import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import BackgroundTasks, Response
from sqlalchemy import select, update

from enterprise.approval.models import ApprovalRequestModel
from enterprise.audit.models import AuditLogModel
from enterprise.auth.models import TaskExtensionModel
from enterprise.procurement import routes
from skyvern.forge.sdk.db.models import TaskModel
from skyvern.forge.sdk.schemas.tasks import TaskStatus
from tests.integration.test_approval01 import database as database
from tests.unit.test_day_11_quotes import _payload, _user

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(
    not os.environ.get("RUN01_TEST_DATABASE_URL"), reason="Requires disposable localhost PostgreSQL",
)]


@pytest.mark.parametrize("variant", ["raise", "lower", "invalid", "timeout"])
async def test_quote_entry_persists_safe_risk_and_approval_atomically(database, monkeypatch, variant):
    engine, sessions = database
    payload = _payload()
    payload.risk = routes.ProcurementRiskInput(is_new_supplier=True, supplier_id="synthetic-supplier")
    result = {"risk_level": "critical" if variant == "raise" else "low"}
    if variant == "invalid":
        result["reason"] = "synthetic-private-marker"
    model = AsyncMock(return_value=result, side_effect=TimeoutError("synthetic-private-marker") if variant == "timeout" else None)
    monkeypatch.setattr(routes, "review_risk", model)
    monkeypatch.setattr(routes.settings, "ENV", "local")
    monkeypatch.setattr(routes, "_allowed_smoke_urls", lambda: {payload.url})
    monkeypatch.setattr(routes, "_create_smoke_task", AsyncMock(return_value=SimpleNamespace(
        task_id="task_a", status=TaskStatus.created,
    )))
    monkeypatch.setattr(routes, "_schedule_approval_notification", Mock())
    async with sessions() as session:
        await session.execute(update(TaskModel).values(status="created"))
        await session.commit()
    response = await routes.quote_task(payload, None, Response(), BackgroundTasks(), "synthetic-risk", _user())
    model.assert_awaited_once()
    await engine.dispose()
    async with sessions() as session:
        extension = await session.scalar(select(TaskExtensionModel))
        approval = await session.get(ApprovalRequestModel, response.approval_id)
        events = (await session.scalars(select(AuditLogModel))).all()
        risk_events = [json.loads(event.input_value) for event in events if event.action_type == "risk_assessed"]
        assert len(risk_events) == 1
        risk = risk_events[0]
        expected = "critical" if variant == "raise" else "high"
        assert risk["risk_level"] == extension.risk_level == approval.risk_level == expected
        assert risk["deterministic_level"] == "high"
        assert risk["llm_fallback"] == (variant in ("invalid", "timeout"))
        assert risk["stage"] == ("deterministic" if risk["llm_fallback"] else "llm")
        assert approval.status == "pending"
        assert approval.approver_department_id == ("compliance" if variant == "raise" else "dept_a")
        assert "synthetic-private-marker" not in str([extension.risk_result, *risk_events])
        assert (await session.get(TaskModel, "task_a")).status == "created"
    # An idempotent retry reuses the saved assessment, not another model review.
    repeated = await routes.quote_task(payload, None, Response(), BackgroundTasks(), "synthetic-risk", _user())
    assert repeated.approval_id == response.approval_id and repeated.idempotent
    model.assert_awaited_once()
