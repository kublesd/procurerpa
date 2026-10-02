"""Synthetic quote boundary checks on disposable PostgreSQL; no provider/browser calls."""

import ast
import json
import os
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from enterprise.audit.models import AuditLogModel
from enterprise.procurement import routes
from enterprise.procurement.models import ProcurementHumanReviewModel, SupplierQuoteModel
from skyvern.forge.sdk.api.llm.schema_validator import validate_and_fill_extraction_result
from skyvern.forge.sdk.db.models import ArtifactModel, TaskModel
from skyvern.forge.sdk.schemas.tasks import TaskStatus
from tests.integration.test_state01_transactions import database as database
from tests.unit.test_day_11_quotes import _user

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(
    not os.environ.get("RUN01_TEST_DATABASE_URL"), reason="Requires disposable localhost PostgreSQL",
)]


@pytest.mark.parametrize("variant", ["normalized", "markdown", "missing_price", "unknown_currency", "artifact", "structure"])
async def test_quote_boundary_persists_only_valid_facts(database, variant):
    engine, sessions = database
    async with sessions() as session:
        task = await session.scalar(select(TaskModel))
        data = {**task.extracted_information, "unit": " UNIT ", "currency": " cNy ", "unit_price_cny": "10.005"}
        if variant == "missing_price":
            del data["unit_price_cny"]
        elif variant == "unknown_currency":
            data["currency"] = "USD"
        elif variant == "markdown":
            data["unit_price_cny"] = "1.0049999999999999999"
            data = "```json\n" + json.dumps(data).replace('"1.0049999999999999999"', "1.0049999999999999999") + "\n```"
        elif variant == "structure":
            data = {"unexpected": "synthetic-private-marker"}
        if variant == "artifact":
            await session.execute(update(ArtifactModel).values(artifact_type="recording"))
        task.extracted_information = validate_and_fill_extraction_result(data, routes.QUOTE_EXTRACTION_SCHEMA)
        await session.commit()
    if variant in ("normalized", "markdown"):
        quote = await routes.recover_quote_task("task_a", _user())
        assert quote.unit_price_cny == Decimal("1.00" if variant == "markdown" else "10.01")
        assert (quote.unit, quote.currency, quote.artifact_id) == ("unit", "CNY", "artifact_a")
        await engine.dispose()
        assert (await routes.recover_quote_task("task_a", _user())).quote_id == quote.quote_id
    else:
        with pytest.raises(HTTPException) as error:
            await routes.recover_quote_task("task_a", _user())
        assert error.value.status_code == 422
        await engine.dispose()
        review_id = error.value.detail["review_id"]
        assert (await routes.get_human_review(review_id, _user())).status == "pending"
        with pytest.raises(HTTPException) as repeated:
            await routes.recover_quote_task("task_a", _user())
        assert repeated.value.status_code == 409
        async with sessions() as session:
            assert await session.scalar(select(SupplierQuoteModel)) is None
            reviews = (await session.scalars(select(ProcurementHumanReviewModel))).all()
            assert len(reviews) == 1
            assert "synthetic-private-marker" not in reviews[0].safe_error_summary
            events = (await session.scalars(select(AuditLogModel))).all()
            assert "synthetic-private-marker" not in str([(e.input_value, e.error_message) for e in events])


@pytest.mark.parametrize("action", ["skip_step", "manual_complete", "terminate"])
async def test_native_retry_exhaustion_enters_durable_human_resolution(database, monkeypatch, action):
    engine, sessions = database
    # Execute the current native method unchanged. Full ForgeAgent import is unavailable
    # because this checkout already deletes workflow/models/block.py.
    path = Path(__file__).resolve().parents[2] / "skyvern/forge/agent.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    agent = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ForgeAgent")
    method = next(node for node in agent.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "handle_failed_step")
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), method], type_ignores=[])
    ast.fix_missing_locations(module)
    native_db = SimpleNamespace(create_step=AsyncMock(side_effect=lambda **values: SimpleNamespace(**values)))
    namespace = dict(
        settings=SimpleNamespace(MAX_RETRIES_PER_STEP=2), LOG=Mock(), TaskStatus=TaskStatus,
        app=SimpleNamespace(DATABASE=native_db, BROWSER_MANAGER=SimpleNamespace(get_for_task=lambda **kw: None)),
        ReachMaxRetriesError=lambda: SimpleNamespace(model_dump=lambda: {"error_code": "reach_max_retries"}),
    )
    exec(compile(module, str(path), "exec"), namespace)
    calls = []

    async def execute_task(**kwargs):
        calls.append(kwargs["task_id"])

        async def update_task(task, status, **fields):
            async with sessions() as session:
                await session.execute(update(TaskModel).where(TaskModel.task_id == task.task_id).values(status=status))
                await session.commit()

        native = SimpleNamespace(
            update_task=update_task,
            summary_failure_reason_for_max_retries=AsyncMock(return_value=SimpleNamespace(errors=[], reasoning="synthetic")),
        )
        task = SimpleNamespace(task_id="task_a", organization_id="org_a", workflow_run_id=None)
        step = SimpleNamespace(order=0, retry_index=0)
        while step is not None:
            step = await namespace["handle_failed_step"](native, SimpleNamespace(max_retries_per_step=2), task, step)

    monkeypatch.setattr(routes.AsyncExecutorFactory, "get_executor", staticmethod(lambda: SimpleNamespace(execute_task=execute_task)))
    with pytest.raises(HTTPException) as failed:
        await routes.recover_quote_task("task_a", _user())
    assert failed.value.status_code == 422
    assert native_db.create_step.await_count == 2
    await engine.dispose()
    review_id = failed.value.detail["review_id"]
    assert (await routes.get_human_review(review_id, _user())).status == "pending"
    outsider = _user().model_copy(update={"org_id": "another_org"})
    with pytest.raises(HTTPException) as denied:
        await routes.get_human_review(review_id, outsider)
    assert denied.value.status_code == 404
    manual = None
    if action == "manual_complete":
        manual = routes.ManualQuoteResult(
            supplier_id="synthetic", material_name="SSD", quantity="10", unit="unit", currency="CNY",
            unit_price_cny="10.00", delivery_days=5, artifact_id="artifact_a",
        )
    body = routes.HumanReviewResolutionRequest(action=action, manual_result=manual)
    await routes.resolve_human_review(review_id, body, _user())
    await engine.dispose()
    if action == "manual_complete":
        assert (await routes.recover_quote_task("task_a", _user())).unit_price_cny == Decimal("10.00")
    else:
        with pytest.raises(HTTPException):
            await routes.recover_quote_task("task_a", _user())
    assert calls == ["task_a"]
    state = await routes.get_quote_state("task_a", _user())
    assert state["state"]["current_step"] == {"skip_step": "skipped", "manual_complete": "completed", "terminate": "terminated"}[action]
