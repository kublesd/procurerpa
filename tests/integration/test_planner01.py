"""Real SQL recovery with synthetic native execution and model output."""

import json
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from enterprise.agent import quote_planner
from enterprise.audit.models import AuditLogModel
from enterprise.procurement import routes
from enterprise.procurement.models import ProcurementCoordinationStateModel as State
from skyvern.forge.sdk.db.models import TaskModel
from tests.integration.test_state01_transactions import database as database
from tests.integration.test_state01_transactions import pytestmark as pytestmark
from tests.unit.test_day_11_quotes import _user


async def test_persisted_plan_replans_after_native_completion_without_replay(database, monkeypatch):
    engine, sessions = database
    calls = []

    async def model(prompt):
        context = json.loads(prompt.split("\n")[-1])
        calls.append(context)
        return {"steps": context["remaining"]}

    monkeypatch.setattr(quote_planner, "call_quote_planner", model)
    persist = routes._persist_extracted_quote
    monkeypatch.setattr(routes, "_persist_extracted_quote", AsyncMock(side_effect=RuntimeError("synthetic outage")))
    with pytest.raises(RuntimeError, match="synthetic outage"):
        await routes.recover_quote_task("task_a", _user())
    async with sessions() as session:
        state = await session.scalar(select(State))
        old_version = state.version
        assert state.current_plan["orchestration"]["source"] == "llm"
    await engine.dispose()
    executor = AsyncMock()
    monkeypatch.setattr(routes.AsyncExecutorFactory, "get_executor", staticmethod(lambda: executor))
    monkeypatch.setattr(routes, "_persist_extracted_quote", persist)
    quote = await routes.recover_quote_task("task_a", _user(), expected_version=old_version)
    assert quote.task_id == "task_a"
    executor.execute_task.assert_not_awaited()
    assert calls == [
        dict(remaining=["execute_native", "persist_quote"], completed=[]),
        dict(remaining=["persist_quote"], completed=["execute_native"]),
    ]
    with pytest.raises(HTTPException) as stale:
        await routes.recover_quote_task("task_a", _user(), expected_version=old_version)
    assert stale.value.status_code == 409
    assert (await routes.recover_quote_task("task_a", _user())).quote_id == quote.quote_id
    assert len(calls) == 2
    async with sessions() as session:
        state = await session.scalar(select(State))
        assert state.current_plan["orchestration"]["steps"] == []
        assert state.completed_subtask_ids == ["execute_native", "persist_quote"]
        assert state.total_replans == state.max_replans == 1
        events = (await session.scalars(select(AuditLogModel).where(
            AuditLogModel.action_type == "quote_plan_updated",
        ).order_by(AuditLogModel.action_index))).all()
        assert [json.loads(event.input_value)["steps"] for event in events] == [
            ["execute_native", "persist_quote"], ["persist_quote"],
        ]


@pytest.mark.parametrize("result", [{"steps": ["submit_order"]}, {"steps": ["execute_native", "persist_quote"]}])
async def test_invalid_replan_preserves_completed_native_fact(database, monkeypatch, result):
    _, sessions = database
    async with sessions() as session:
        await session.execute(update(TaskModel).values(status="completed"))
        await session.commit()
    monkeypatch.setattr(quote_planner, "call_quote_planner", AsyncMock(return_value=result))
    executor = AsyncMock()
    monkeypatch.setattr(routes.AsyncExecutorFactory, "get_executor", staticmethod(lambda: executor))
    quote = await routes.recover_quote_task("task_a", _user())
    assert quote.task_id == "task_a"
    executor.execute_task.assert_not_awaited()
    async with sessions() as session:
        state = await session.scalar(select(State))
        assert state.current_plan["orchestration"]["source"] == "deterministic_fallback"


async def test_plan_cas_rejects_stale_write_and_stale_noop(database):
    _, sessions = database
    initial = dict(steps=["execute_native", "persist_quote"], completed=[], source="llm")
    revised = dict(steps=["persist_quote"], completed=["execute_native"], source="llm")
    args = dict(task_id="task_a", org_id="org_a", department_id="dept_a", executor="user_a")
    async with sessions() as session:
        await routes.save_quote_plan(session, **args, plan=initial)
        await session.commit()
    async with sessions() as first, sessions() as stale, sessions() as noop:
        stale_row = await routes.load_quote_state(stale, "task_a", "org_a")
        noop_row = await routes.load_quote_state(noop, "task_a", "org_a")
        await routes.save_quote_plan(first, **args, plan=revised)
        await first.commit()
        assert stale_row.version == noop_row.version == 2
        for session, plan in ((stale, revised), (noop, initial)):
            with pytest.raises(HTTPException) as conflict:
                await routes.save_quote_plan(session, **args, plan=plan)
            assert conflict.value.status_code == 409
            await session.rollback()


async def test_human_completion_does_not_invent_native_completion(database):
    _, sessions = database
    args = dict(task_id="task_a", org_id="org_a", department_id="dept_a", executor="user_a")
    async with sessions() as session:
        await routes.save_quote_plan(
            session, **args, plan=dict(steps=["execute_native", "persist_quote"], completed=[], source="llm"),
        )
        await session.execute(update(TaskModel).values(status="running"))
        await routes.advance_quote_state(session, **args, step="needs_human")
        await session.commit()
    async with sessions() as session:
        await routes.advance_quote_state(session, **args, step="completed")
        await session.commit()
    async with sessions() as session:
        state = await session.scalar(select(State))
        assert state.completed_subtask_ids == ["persist_quote"]
        assert state.current_plan["orchestration"]["steps"] == []
