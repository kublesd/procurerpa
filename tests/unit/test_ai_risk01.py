"""Synthetic risk boundary checks; provider and browser calls are replaced."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import BackgroundTasks, HTTPException, Response

from enterprise.approval.risk_detector import detect_risk
from enterprise.approval.risk_review import RISK_MODEL_KEY, review_risk
from enterprise.procurement import routes
from skyvern.forge.sdk.api.llm import api_handler_factory as native
from skyvern.forge.sdk.api.llm.models import LLMConfig
from skyvern.forge.sdk.schemas.tasks import TaskStatus
from tests.unit.test_day_11_quotes import _payload, _user
from tests.unit.test_risk_detector import _context


@pytest.mark.asyncio
async def test_low_risk_skips_and_hit_sends_only_server_categories():
    model = AsyncMock(return_value={"risk_level": "critical"})
    low = await detect_risk(_context(redacted_description="synthetic-private-marker"), model, structured_only=True)
    assert low.risk_level == "low"
    model.assert_not_awaited()
    result = await detect_risk(_context(
        total_amount_cny="123456.78", supplier_id="private-supplier",
        redacted_description="Token synthetic-private-marker bank 6222000000000000 webhook https://private.invalid",
    ), model, structured_only=True)
    prompt = model.await_args.args[0]
    body = json.loads(prompt.split("\n", 1)[1])
    assert set(body) == {"deterministic_level", "categories"}
    for value in ("123456.78", "private-supplier", "synthetic-private-marker", "6222000000000000", "private.invalid"):
        assert value not in prompt
    assert len(prompt) < 2048
    assert result.risk_level == "critical" and result.stage == "llm"


@pytest.mark.asyncio
@pytest.mark.parametrize("output", [None, [], {"risk_level": []}, {"risk_level": "unknown"},
                                         {"risk_level": "critical", "reason": "synthetic-private-marker"}])
async def test_invalid_output_is_not_persisted_and_cannot_lower_risk(output):
    result = await detect_risk(_context(total_amount_cny="1000000"), AsyncMock(return_value=output), structured_only=True)
    assert result.risk_level == "critical" and result.llm_fallback
    assert "synthetic-private-marker" not in str(result.to_dict())


@pytest.mark.asyncio
async def test_lower_result_and_timeout_keep_deterministic_floor(monkeypatch):
    context = _context(is_new_supplier=True)
    result = await detect_risk(context, AsyncMock(return_value={"risk_level": "low"}), structured_only=True)
    assert result.risk_level == result.deterministic_level == "high"
    from enterprise.approval import risk_detector

    async def timeout(awaitable, timeout):
        assert timeout == 15
        awaitable.close()
        raise TimeoutError("synthetic-private-marker")

    monkeypatch.setattr(risk_detector.asyncio, "wait_for", timeout)
    result = await detect_risk(context, AsyncMock(), structured_only=True)
    assert result.risk_level == "high" and result.llm_fallback
    assert "synthetic-private-marker" not in str(result.to_dict())


@pytest.fixture
def native_boundary(monkeypatch):
    config = LLMConfig("gemini/gemini-2.5-flash", [], False, False)
    monkeypatch.setattr(native.LLMConfigRegistry, "_configs", {RISK_MODEL_KEY: config})
    provider = AsyncMock(return_value=native.ModelResponse(choices=[{
        "index": 0, "finish_reason": "stop",
        "message": {"role": "assistant", "content": '{"risk_level":"high"}'},
    }], model="gemini/gemini-2.5-flash"))
    monkeypatch.setattr(native.litellm, "acompletion", provider)
    artifacts = SimpleNamespace(prepare_llm_artifact=AsyncMock(), bulk_create_artifacts=AsyncMock())
    monkeypatch.setattr(native, "app", SimpleNamespace(ARTIFACT_MANAGER=artifacts))
    parser = Mock(side_effect=AssertionError("Generic repair parser must not run"))
    monkeypatch.setattr(native, "parse_api_response", parser)
    monkeypatch.setattr(native, "skyvern_context", SimpleNamespace(
        current=Mock(side_effect=AssertionError("No inherited context")),
    ))
    return provider, artifacts


@pytest.mark.asyncio
async def test_native_review_uses_registered_model_without_artifacts_or_history(native_boundary):
    provider, artifacts = native_boundary
    assert await review_risk("Synthetic categories") == {"risk_level": "high"}
    assert provider.await_args.kwargs["model"] == "gemini/gemini-2.5-flash"
    assert provider.await_args.kwargs["no-log"] is True
    assert provider.await_args.kwargs["cache"] == {"no-cache": True, "no-store": True}
    assert provider.await_args.kwargs["max_completion_tokens"] == 2048
    assert provider.await_args.kwargs["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "Synthetic categories"}]},
    ]
    artifacts.prepare_llm_artifact.assert_not_awaited()
    artifacts.bulk_create_artifacts.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["history", "logging"])
async def test_strict_native_mode_rejects_unsafe_options(native_boundary, monkeypatch, mode):
    provider, _ = native_boundary
    handler = native.LLMAPIHandlerFactory.get_llm_api_handler(RISK_MODEL_KEY, strict_response=True)
    if mode == "logging":
        monkeypatch.setattr(native.litellm, "global_disable_no_log_param", True)
    with pytest.raises(ValueError):
        await handler(prompt="Synthetic", prompt_name="procurement-risk-review", use_message_history=mode == "history")
    provider.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["synthetic-private-marker", "x" * 4097, None], ids=["invalid", "oversized", "empty"])
async def test_native_invalid_response_raises_only_safe_error(native_boundary, content):
    provider, artifacts = native_boundary
    provider.return_value.choices[0].message.content = content
    with pytest.raises(ValueError, match="^Invalid structured model response$"):
        await review_risk("Synthetic categories")
    artifacts.bulk_create_artifacts.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_model_does_not_fall_back_to_another_provider(monkeypatch):
    monkeypatch.setattr(native.LLMConfigRegistry, "_configs", {})
    with pytest.raises(ValueError, match="unavailable"):
        await review_risk("Synthetic categories")


@pytest.mark.asyncio
async def test_default_native_handler_keeps_existing_parser(native_boundary, monkeypatch):
    _, artifacts = native_boundary
    parser = Mock(return_value={"existing": "parsed"})
    monkeypatch.setattr(native, "parse_api_response", parser)
    monkeypatch.setattr(native, "skyvern_context", SimpleNamespace(current=lambda: None))
    monkeypatch.setattr(native.litellm, "completion_cost", lambda **kwargs: 0)
    handler = native.LLMAPIHandlerFactory.get_llm_api_handler(RISK_MODEL_KEY)
    assert await handler(prompt="Synthetic", prompt_name="existing") == {"existing": "parsed"}
    parser.assert_called_once()
    artifacts.bulk_create_artifacts.assert_awaited_once_with([])


@pytest.mark.asyncio
@pytest.mark.parametrize("denied", ["organization", "permission", "length", None])
async def test_quote_route_checks_boundaries_before_review(monkeypatch, denied):
    payload = _payload()
    model = AsyncMock(return_value={"risk_level": "high"})
    monkeypatch.setattr(routes, "review_risk", model)
    monkeypatch.setattr(routes.settings, "ENV", "local")
    monkeypatch.setattr(routes, "_allowed_smoke_urls", lambda: {payload.url})
    validate = AsyncMock(side_effect=HTTPException(403) if denied == "permission" else None)
    monkeypatch.setattr(routes, "_validate_smoke_context", validate)
    monkeypatch.setattr(routes, "_persisted_request", AsyncMock(return_value=None))
    monkeypatch.setattr(routes, "_create_smoke_task", AsyncMock(return_value=SimpleNamespace(
        task_id="task_a", status=TaskStatus.created,
    )))
    attach = AsyncMock(return_value="approval_a")
    monkeypatch.setattr(routes, "_attach_procurement_context", attach)
    monkeypatch.setattr(routes, "_schedule_approval_notification", Mock())
    if denied == "organization":
        payload.organization_id = "other_org"
    if denied == "length":
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            routes.ProcurementRiskInput(redacted_description="x" * 2001)
    elif denied:
        with pytest.raises(HTTPException) as error:
            await routes.quote_task(payload, None, Response(), BackgroundTasks(), "synthetic-key", _user())
        assert error.value.status_code == 403
    else:
        result = await routes.quote_task(payload, None, Response(), BackgroundTasks(), "synthetic-key", _user())
        assert result.approval_id == "approval_a"
        risk = attach.await_args.args[3]
        assert risk.stage == "llm" and risk.risk_level == "high"
        model.assert_awaited_once()
        return
    model.assert_not_awaited()
