"""S7 real Skyvern model routing checks."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from enterprise.agent import skyvern_handler as handler_module
from enterprise.audit.models import AuditLogModel
from enterprise.llm.action_cache import build_cache_key
from enterprise.llm.model_router import (
    ModelRoutingUnavailable,
    ModelTier,
    ProcurementPageKind,
    resolve_procurement_page,
)
from enterprise.procurement.models import ProcurementHumanReviewModel
from skyvern.config import settings
from skyvern.forge.agent import ForgeAgent
from tests.unit.test_s3_skyvern_executor import Database, make_handler

MODEL_MAPPING = {
    "light-model": {"llm_key": "LIGHT_KEY", "label": "Light"},
    "standard-model": {"llm_key": "STANDARD_KEY", "label": "Standard"},
    "heavy-model": {"llm_key": "HEAVY_KEY", "label": "Heavy"},
}


def configure_tiers(monkeypatch):
    monkeypatch.setattr(settings, "PROCUREMENT_LIGHT_LLM_KEY", "LIGHT_KEY")
    monkeypatch.setattr(settings, "PROCUREMENT_STANDARD_LLM_KEY", "STANDARD_KEY")
    monkeypatch.setattr(settings, "PROCUREMENT_HEAVY_LLM_KEY", "HEAVY_KEY")


def test_three_page_kinds_resolve_to_configured_native_models(monkeypatch):
    configure_tiers(monkeypatch)
    expected = {
        ProcurementPageKind.SUPPLIER_CATALOG: ModelTier.LIGHT,
        ProcurementPageKind.DYNAMIC_QUOTE_PORTAL: ModelTier.STANDARD,
        ProcurementPageKind.ERP_CONTRACT: ModelTier.HEAVY,
    }

    for page_kind, tier in expected.items():
        decision = resolve_procurement_page(
            page_kind,
            available_keys={"LIGHT_KEY", "STANDARD_KEY", "HEAVY_KEY"},
            model_mapping=MODEL_MAPPING,
        )
        assert decision.model_tier == tier
        assert decision.resolved_model_key == f"{tier.value.upper()}_KEY"
        assert decision.execution_mode == "real"
        assert decision.connection_status == "connected"


def test_heavy_route_falls_back_only_to_configured_standard_then_light(monkeypatch):
    configure_tiers(monkeypatch)
    decision = resolve_procurement_page(
        ProcurementPageKind.ERP_CONTRACT,
        available_keys={"STANDARD_KEY", "LIGHT_KEY"},
        model_mapping=MODEL_MAPPING,
    )

    assert decision.resolved_model_key == "STANDARD_KEY"
    assert decision.reason_code == "heavy_fallback_to_standard"
    with pytest.raises(ModelRoutingUnavailable):
        resolve_procurement_page(
            ProcurementPageKind.ERP_CONTRACT,
            available_keys=set(),
            model_mapping=MODEL_MAPPING,
        )


def test_action_cache_key_isolated_by_resolved_model():
    args = ("org_a", "dom_hash", "goal_hash")
    assert build_cache_key(*args, "LIGHT_KEY", "v1") != build_cache_key(*args, "HEAVY_KEY", "v1")


@pytest.mark.asyncio
async def test_real_step_call_records_only_safe_route_metadata():
    agent = ForgeAgent()
    audit = AsyncMock()
    agent._audit_procurement_model_call = audit
    task = SimpleNamespace(
        task_id="task_a",
        organization_id="org_a",
        model={"llm_key": "STANDARD_KEY", "model_tier": "standard", "reason_code": "tier_selected"},
    )
    step = SimpleNamespace(step_id="step_a", order=2)
    page = SimpleNamespace(screenshots=[])
    llm = AsyncMock(return_value={"actions": [{"action_type": "WAIT"}]})

    result = await agent._resolve_action_response(
        task=task,
        step=step,
        scraped_page=page,
        llm_api_handler=llm,
        prompt="synthetic prompt that must not be audited",
        prompt_name="extract-actions",
    )

    assert result["actions"][0]["action_type"] == "WAIT"
    audit.assert_awaited_once()
    assert audit.await_args.args[:2] == (task, step)
    assert "prompt" not in audit.await_args.kwargs


@pytest.mark.asyncio
async def test_native_handler_passes_model_to_task_and_writes_safe_route_audit(monkeypatch):
    from skyvern.forge.sdk.api.llm.config_registry import LLMConfigRegistry
    configure_tiers(monkeypatch)
    monkeypatch.setattr(LLMConfigRegistry, "get_model_names", lambda: list({"LIGHT_KEY", "STANDARD_KEY", "HEAVY_KEY"}))
    monkeypatch.setattr(type(settings), "get_model_name_to_llm_key", lambda self: MODEL_MAPPING)
    database, calls = Database(), []
    result = await make_handler(database, calls)("ignored", {})

    request = calls[0]["task"]
    assert request.llm_key == request.model["llm_key"]
    assert result["model_alias"].startswith("procurement-")
    route_audit = next(
        row for row in database.rows if isinstance(row, AuditLogModel) and row.action_type == "model_route"
    )
    details = json.loads(route_audit.input_value)
    assert details == {
        "model_tier": result["model_tier"],
        "resolved_model_key": request.model["llm_key"],
        "reason_code": result["routing_reason_code"],
        "step_id": None,
    }
    assert "API_KEY" not in result


@pytest.mark.asyncio
async def test_no_configured_model_creates_review_without_running_llm(monkeypatch):
    database, calls = Database(), []

    def unavailable(_page_kind):
        raise ModelRoutingUnavailable("procurement_model_unavailable")

    monkeypatch.setattr(handler_module, "resolve_procurement_page", unavailable)
    result = await make_handler(database, calls)("ignored", {})

    assert result["error"] == "procurement_model_unavailable"
    assert calls[0]["defer_execution"] is True
    assert any(
        isinstance(row, ProcurementHumanReviewModel)
        and row.reason_code == "procurement_model_unavailable"
        for row in database.rows
    )


@pytest.mark.asyncio
async def test_real_step_model_call_audit_contains_only_safe_routing_fields():
    session = AsyncMock()
    session.scalar.return_value = SimpleNamespace(department_id="dept_a")
    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=session)
    session_context.__aexit__ = AsyncMock(return_value=None)
    database = SimpleNamespace(Session=MagicMock(return_value=session_context))
    writer = AsyncMock()
    task = SimpleNamespace(
        task_id="tsk_a",
        organization_id="org_a",
        model={"llm_key": "STANDARD_KEY", "model_tier": "standard", "reason_code": "tier_selected"},
    )
    step = SimpleNamespace(step_id="step_a", order=2)

    with patch("skyvern.forge.agent.app", SimpleNamespace(DATABASE=database)), patch(
        "skyvern.forge.agent.write_audit_log", writer
    ):
        await ForgeAgent._audit_procurement_model_call(task, step, 123, "success")

    details = writer.await_args.kwargs["input_value"]
    assert details == {
        "model_tier": "standard",
        "resolved_model_key": "STANDARD_KEY",
        "reason_code": "tier_selected",
        "step_id": "step_a",
    }
    assert writer.await_args.kwargs["duration_ms"] == 123


def test_runtime_features_use_native_tree_without_page_text_or_values():
    from enterprise.llm.model_router import runtime_page_features, safe_feature_summary
    page = SimpleNamespace(element_tree=[{"tagName": "iframe", "children": [
        {"tagName": "iframe", "children": [{"tagName": "input", "shadowHost": "synthetic", "attributes": {"value": "secret-sentinel"}, "text": "private-sentinel"}]}
    ]}])
    features = runtime_page_features(page)
    assert (features.element_count, features.iframe_depth, features.form_field_count, features.has_shadow_dom) == (3, 2, 1, True)
    summary = json.dumps(safe_feature_summary(features))
    assert "sentinel" not in summary and "synthetic" not in summary
    assert "not_observed" in summary
    assert runtime_page_features(SimpleNamespace(element_tree=[])) is None
    assert runtime_page_features(SimpleNamespace(element_tree=[{"tagName": "div", "children": "bad"}])) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("workflow_run_id", [None, "wfr_synthetic"])
async def test_runtime_route_precedes_prompt_and_uses_isolated_task_copy(monkeypatch, workflow_run_id):
    from enterprise.llm.model_router import PageFeatures, resolve_model
    configure_tiers(monkeypatch)
    decision = resolve_model(PageFeatures(element_count=501), available_keys={"STANDARD_KEY"}, model_mapping=MODEL_MAPPING)
    assert decision.model_tier == ModelTier.STANDARD
    agent = ForgeAgent()
    agent._procurement_context = AsyncMock(return_value=SimpleNamespace(department_id="dept_a"))
    task = SimpleNamespace(task_id="task_a", organization_id="org_a", workflow_run_id=workflow_run_id,
                           model={"procurement_routing": "runtime-v1"})
    step = SimpleNamespace(step_id="step_a", order=0)
    session = AsyncMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=None)
    with patch("skyvern.forge.agent.app", SimpleNamespace(DATABASE=SimpleNamespace(Session=lambda: context))), patch(
        "skyvern.forge.agent.resolve_model", return_value=decision
    ), patch("skyvern.forge.agent.write_audit_log", AsyncMock()) as audit:
        await agent._route_procurement_step(task, step, SimpleNamespace(element_tree=[{"tagName": "div"}]))
    assert step.procurement_model_route["llm_key"] == "STANDARD_KEY"
    assert step.procurement_model_route["feature_source"] == "native_scrape"
    assert step.procurement_model_route["cache_policy"] == ("disabled" if workflow_run_id else "safe_actions_only")
    assert task.model == {"procurement_routing": "runtime-v1"}
    assert audit.await_args.kwargs["commit"] is False
    assert audit.await_args.kwargs["business_object_id"] == "step_a"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["CLICK", "INPUT_TEXT", "UPLOAD_FILE", "KEYPRESS", "COMPLETE"])
async def test_procurement_decisions_never_enter_action_cache(action):
    cache = SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock())
    agent = ForgeAgent(action_cache=cache)
    agent._audit_procurement_model_call = AsyncMock()
    step = SimpleNamespace(step_id="s", order=0, procurement_model_route={"llm_key": "LIGHT_KEY", "cache_policy": "safe_actions_only"})
    task = SimpleNamespace(organization_id="org_a", task_id="t", llm_key="INITIAL_KEY", navigation_goal="synthetic")
    page = SimpleNamespace(screenshots=[], build_element_tree=lambda _: "<div />")
    with patch("skyvern.forge.agent.parse_actions", return_value=[object()]):
        await agent._resolve_action_response(task=task, step=step, scraped_page=page,
            llm_api_handler=AsyncMock(return_value={"actions": [{"action_type": action}]}), prompt="synthetic", prompt_name="extract-actions")
    cache.set.assert_not_awaited()
    assert cache.get.await_args.args[0] == build_cache_key("org_a", __import__("hashlib").sha256(b"<div />").hexdigest(),
        __import__("hashlib").sha256(b"synthetic").hexdigest(), "LIGHT_KEY")


def test_restored_native_block_keeps_enterprise_secret_template_boundary():
    from skyvern.forge.sdk.workflow.models.block import Block
    context = SimpleNamespace(workflow=SimpleNamespace(description="enterprise-skill/v1"), include_secrets_in_templates=False)
    with pytest.raises(ValueError, match="secret templates"):
        Block.format_block_parameter_template_from_workflow_run_context(
            SimpleNamespace(), "synthetic", context, force_include_secrets=True)


@pytest.mark.asyncio
async def test_form_route_never_looks_up_or_writes_action_cache():
    cache = SimpleNamespace(get=AsyncMock(), set=AsyncMock())
    agent = ForgeAgent(action_cache=cache)
    agent._audit_procurement_model_call = AsyncMock()
    step = SimpleNamespace(step_id="s", order=0, procurement_model_route={"llm_key": "LIGHT_KEY", "cache_policy": "disabled"})
    task = SimpleNamespace(organization_id="org_a", task_id="t", llm_key="LIGHT_KEY", navigation_goal="synthetic")
    result = await agent._resolve_action_response(task=task, step=step, scraped_page=SimpleNamespace(screenshots=[]),
        llm_api_handler=AsyncMock(return_value={"actions": [{"action_type": "WAIT"}]}), prompt="synthetic", prompt_name="extract-actions")
    assert result["actions"][0]["action_type"] == "WAIT"
    cache.get.assert_not_awaited()
    cache.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_cache_reuses_only_same_registered_key_and_audits_hit():
    from fakeredis.aioredis import FakeRedis

    from enterprise.llm.action_cache import RedisActionCacheStore
    redis = FakeRedis(decode_responses=True)
    agent = ForgeAgent(action_cache=RedisActionCacheStore(redis))
    agent._audit_procurement_model_call = AsyncMock()
    step = SimpleNamespace(step_id="s", order=0, procurement_model_route={"llm_key": "LIGHT_KEY", "cache_policy": "safe_actions_only"})
    task = SimpleNamespace(organization_id="org_a", task_id="t", llm_key="INITIAL_KEY", navigation_goal="synthetic")
    page = SimpleNamespace(screenshots=[], build_element_tree=lambda _: "<div />")
    llm = AsyncMock(return_value={"actions": [{"action_type": "WAIT"}]})
    try:
        with patch("skyvern.forge.agent.parse_actions", return_value=[object()]):
            for _ in range(2):
                await agent._resolve_action_response(task=task, step=step, scraped_page=page,
                    llm_api_handler=llm, prompt="synthetic", prompt_name="extract-actions")
            assert llm.await_count == 1
            assert agent._audit_procurement_model_call.await_args.args[-1] == "cache_hit"
            step.procurement_model_route["llm_key"] = "HEAVY_KEY"
            await agent._resolve_action_response(task=task, step=step, scraped_page=page,
                llm_api_handler=llm, prompt="synthetic", prompt_name="extract-actions")
            assert llm.await_count == 2
            assert (await agent.action_cache.stats("org_a"))["hits"] == 1
    finally:
        await redis.aclose()
