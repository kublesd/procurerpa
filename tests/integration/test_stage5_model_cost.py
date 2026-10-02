"""Disposable PostgreSQL and native scrape/prompt entry; synthetic provider/browser only."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from enterprise.audit.models import AuditLogModel
from enterprise.dashboard import routes as dashboard
from enterprise.procurement import routes
from skyvern.config import settings
from skyvern.forge import agent as native
from skyvern.forge.sdk.api.llm.config_registry import LLMConfigRegistry
from skyvern.forge.sdk.db.models import StepModel, TaskModel
from skyvern.forge.sdk.models import Step
from skyvern.forge.sdk.schemas.tasks import Task
from skyvern.schemas.runs import RunEngine
from tests.integration import test_state01_transactions as state01
from tests.unit.test_day_11_quotes import _user

stage5_database = state01.database

pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(
    not os.environ.get("RUN01_TEST_DATABASE_URL"), reason="Requires disposable PostgreSQL")]


async def test_native_scrape_route_persists_and_dashboard_uses_each_step_model(stage5_database, monkeypatch):
    engine, sessions = stage5_database
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: StepModel.__table__.create(conn))
    monkeypatch.setattr(native, "app", routes.forge_app)
    monkeypatch.setattr(dashboard, "forge_app", routes.forge_app)
    monkeypatch.setattr(dashboard, "get_persistent_cache_store", lambda: None)
    for tier in ("LIGHT", "STANDARD", "HEAVY"):
        monkeypatch.setattr(settings, f"PROCUREMENT_{tier}_LLM_KEY", f"{tier}_KEY")
    monkeypatch.setattr(LLMConfigRegistry, "get_model_names", lambda: ["LIGHT_KEY", "STANDARD_KEY", "HEAVY_KEY"])
    async with sessions() as session:
        row = await session.get(TaskModel, "task_a")
        row.model = {"procurement_routing": "runtime-v1"}
        session.add_all([StepModel(step_id=step_id, task_id="task_a", organization_id="org_a", status="running", order=index,
                                  input_token_count=100, output_token_count=20, cached_token_count=10,
                                  step_cost=cost) for index, (step_id, cost) in enumerate((("step_light", "0.01"), ("step_heavy", "0.02")))])
        await session.commit()
        task = Task.model_validate({column.name: getattr(row, column.name) for column in row.__table__.columns})
        steps = [Step.model_validate({column.name: getattr(step, column.name) for column in step.__table__.columns})
                 for step in (await session.scalars(select(StepModel).order_by(StepModel.order))).all()]
    agent = native.ForgeAgent()
    agent.async_operation_pool.run_operation = MagicMock()
    agent._persist_scrape_artifacts = AsyncMock()
    for step, count, expected in zip(steps, (80, 501), ("LIGHT_KEY", "HEAVY_KEY")):
        page = SimpleNamespace(element_tree=[{"tagName": "div", "text": "synthetic-private"} for _ in range(count)], elements=[{}] * count)
        agent._scrape_with_type = AsyncMock(return_value=page)
        async def prompt(routed_task, current_step, *_args, **_kwargs):
            assert routed_task.llm_key == expected
            assert current_step.procurement_model_route["llm_key"] == expected
            assert task.model == {"procurement_routing": "runtime-v1"}
            return "synthetic prompt", False, "extract-actions"
        agent._build_extract_action_prompt = AsyncMock(side_effect=prompt)
        await agent.build_and_record_step_prompt(task, step, None, RunEngine.skyvern_v1)
        agent._scrape_with_type.assert_awaited_once()
    await engine.dispose()  # Read only the persisted attribution after connection restart.
    response = await dashboard.get_cost_estimation(_user())
    assert response.total_tokens == 240 and response.total_cost_usd == 0.03
    assert {item.model_tier for item in response.breakdown} == {"light", "heavy"}
    async with sessions() as session:
        audits = (await session.scalars(select(AuditLogModel).where(AuditLogModel.action_type == "model_route"))).all()
        assert len(audits) == 2
        assert "synthetic-private" not in str([audit.input_value for audit in audits])
    outsider = _user().model_copy(update={"org_id": "org_b"})
    assert (await dashboard.get_cost_estimation(outsider)).breakdown == []
    restricted = _user().model_copy(update={"procurement_category_ids": ["not-visible"]})
    assert (await dashboard.get_cost_estimation(restricted)).breakdown == []
    restricted = _user().model_copy(update={"department_roles": []})
    assert (await dashboard.get_cost_estimation(restricted)).breakdown == []
