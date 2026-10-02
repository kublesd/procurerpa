import json
from unittest.mock import AsyncMock

import pytest

from enterprise.agent import quote_planner as planner


@pytest.mark.asyncio
async def test_plan_resume_and_replan_exclude_completed_steps(monkeypatch):
    caller = AsyncMock(return_value={"steps": list(planner.STEPS)})
    monkeypatch.setattr(planner, "call_quote_planner", caller)
    initial = await planner.plan_quote(native_completed=False)
    assert initial == dict(steps=list(planner.STEPS), completed=[], source="llm")
    assert await planner.plan_quote(native_completed=False, previous=initial) == initial
    assert caller.await_count == 1
    caller.return_value = {"steps": ["persist_quote"]}
    revised = await planner.plan_quote(native_completed=True, previous=initial)
    assert revised == dict(steps=["persist_quote"], completed=["execute_native"], source="llm")
    context = json.loads(caller.call_args.args[0].split("\n")[-1])
    assert context == dict(remaining=["persist_quote"], completed=["execute_native"])
    assert await planner.plan_quote(native_completed=True, previous=revised) == revised
    assert caller.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [
    {}, {"steps": []}, {"steps": ["execute_native", "persist_quote"]},
    {"steps": ["persist_quote"], "secret": "synthetic-private"},
    {"steps": ["submit_order"]}, "synthetic-private", None,
])
async def test_replan_rejects_replay_and_non_allowlisted_output(monkeypatch, result):
    monkeypatch.setattr(planner, "call_quote_planner", AsyncMock(return_value=result))
    plan = await planner.plan_quote(native_completed=True)
    assert plan == dict(steps=["persist_quote"], completed=["execute_native"], source="deterministic_fallback")


@pytest.mark.asyncio
async def test_failure_does_not_leak_or_block_existing_chain(monkeypatch, caplog):
    caller = AsyncMock(side_effect=RuntimeError("synthetic-private"))
    monkeypatch.setattr(planner, "call_quote_planner", caller)
    plan = await planner.plan_quote(native_completed=False, previous={"steps": ["submit_order"]})
    assert plan == dict(steps=list(planner.STEPS), completed=[], source="deterministic_fallback")
    assert "synthetic-private" not in caplog.text + json.dumps(plan) + caller.call_args.args[0]


@pytest.mark.asyncio
async def test_native_adapter_requires_registered_model_and_strict_response(monkeypatch):
    from skyvern.forge.sdk.api.llm.api_handler_factory import LLMAPIHandlerFactory
    from skyvern.forge.sdk.api.llm.config_registry import LLMConfigRegistry

    monkeypatch.setattr(LLMConfigRegistry, "get_model_names", lambda: [])
    with pytest.raises(ValueError, match="unavailable"):
        await planner.call_quote_planner("safe-enumerations")
    monkeypatch.setattr(LLMConfigRegistry, "get_model_names", lambda: ["GEMINI_2.5_FLASH"])
    handler = AsyncMock(return_value={"steps": list(planner.STEPS)})

    def factory(key, *, strict_response):
        assert key == "GEMINI_2.5_FLASH" and strict_response is True
        return handler

    monkeypatch.setattr(LLMAPIHandlerFactory, "get_llm_api_handler", factory)
    assert await planner.call_quote_planner("safe-enumerations") == {"steps": list(planner.STEPS)}
    assert handler.call_args.kwargs == dict(
        prompt="safe-enumerations", prompt_name="procurement-quote-plan",
        parameters={"max_completion_tokens": 2048, "temperature": 0, "timeout": 12},
    )


@pytest.mark.asyncio
async def test_native_template_plans_resume_only_server_owned_suffix(monkeypatch):
    steps = ("login_0", "table_extract_1", "file_download_2")
    caller = AsyncMock(return_value={"steps": ["table_extract_1", "file_download_2"]})
    monkeypatch.setattr(planner, "call_quote_planner", caller)
    plan = await planner.plan_steps(steps, completed=["login_0"])
    assert plan["source"] == "llm"
    assert await planner.plan_steps(steps, completed=["login_0"], previous=plan) == plan
    assert caller.await_count == 1
    with pytest.raises(ValueError, match="completion sequence"):
        await planner.plan_steps(steps, completed=["file_download_2"])
