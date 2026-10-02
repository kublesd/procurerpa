"""Review regressions at native input, browser, Artifact and extraction boundaries."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from enterprise.skills.executor import SkillStep, compile_skill_pipeline
from enterprise.skills.native import compile_native_skills
from enterprise.workflows import runtime
from skyvern.forge.sdk.api.llm.schema_validator import validate_and_fill_extraction_result
from skyvern.forge.sdk.artifact.models import ArtifactType
from skyvern.forge.sdk.workflow.context_manager import WorkflowRunContext
from skyvern.webeye import browser_factory
from skyvern.webeye.actions import handler


@pytest.mark.asyncio
@pytest.mark.parametrize("page_url,frame_url,allowed", [
    ("http://controlled/login", "http://controlled/login", True),
    ("http://controlled/login", "http://foreign/frame", False),
    ("http://controlled/login", "about:blank", False),
    ("http://foreign/page", "http://controlled/login", False),
])
async def test_credential_fill_checks_actual_frame(monkeypatch, page_url, frame_url, allowed):
    context = WorkflowRunContext("demo", "wf_demo", "wp_demo", "wfr_demo", None,
                                 SimpleNamespace(description=runtime.MARKER))
    context.organization_id = "org_demo"
    context.secrets["placeholder_demo"] = "synthetic-only-password"
    session = AsyncMock()
    app = SimpleNamespace(
        DATABASE=SimpleNamespace(Session=lambda: session),
        WORKFLOW_CONTEXT_MANAGER=SimpleNamespace(get_workflow_run_context=lambda _: context),
    )
    monkeypatch.setattr(handler, "app", app)
    monkeypatch.setattr(runtime, "app", app)
    monkeypatch.setattr(runtime, "load_native_instance", AsyncMock(return_value=SimpleNamespace(
        status="running", organization_id="org_demo",
        state={"url": "http://controlled/login", "credential_id": "cred_demo", "credential_revision": "v1"},
    )))
    monkeypatch.setattr(runtime, "authorized_actor", AsyncMock())
    monkeypatch.setattr(runtime, "credential_metadata", AsyncMock())
    element = SimpleNamespace(
        get_frame=lambda: SimpleNamespace(url=frame_url), get_tag_name=lambda: "input",
        get_locator=lambda: None, input_fill=AsyncMock(),
    )
    monkeypatch.setattr(handler, "DomUtil", lambda *_: SimpleNamespace(
        get_skyvern_element_by_id=AsyncMock(return_value=element)))
    monkeypatch.setattr(handler.SkyvernFrame, "create_instance", AsyncMock())
    monkeypatch.setattr(handler, "IncrementalScrapePage", lambda **_: None)
    monkeypatch.setattr(handler, "get_input_value", AsyncMock(return_value=""))
    call = handler.handle_input_text_action(
        SimpleNamespace(element_id="password", text="placeholder_demo", totp_timing_info=None),
        SimpleNamespace(url=page_url), SimpleNamespace(id_to_element_dict={"password": {"tagName": "input"}}),
        SimpleNamespace(workflow_run_id="wfr_demo"), None,
    )
    if allowed:
        assert (await call)[0].success
        element.input_fill.assert_awaited_once_with(text="synthetic-only-password")
    else:
        with pytest.raises(HTTPException) as error:
            await call
        assert error.value.status_code == 409
        element.input_fill.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("enterprise", [True, False])
@pytest.mark.parametrize("browser_type", ["chromium-headless", "chromium-headful", "cdp-connect"])
async def test_browser_creation_disables_enterprise_recording(monkeypatch, enterprise, browser_type):
    monkeypatch.setattr(runtime, "current_native_context", lambda: object() if enterprise else None)
    for name, value in {
        "BROWSER_TYPE": browser_type, "BROWSER_LOGS_ENABLED": True,
        "CHROME_EXECUTABLE_PATH": None, "EXTENSIONS": [], "ENABLE_PROXY": False,
    }.items():
        monkeypatch.setattr(browser_factory.settings, name, value)
    monkeypatch.setattr(browser_factory, "make_temp_directory", lambda **_: "synthetic-profile")
    monkeypatch.setattr(browser_factory, "initialize_download_dir", lambda: "synthetic-downloads")
    monkeypatch.setattr(browser_factory.BrowserContextFactory, "update_chromium_browser_preferences", lambda **_: None)
    monkeypatch.setattr(browser_factory, "set_download_file_listener", lambda **_: None)
    console = Mock()
    monkeypatch.setattr(browser_factory, "set_browser_console_log", console)
    existing, fresh = object(), object()
    browser = SimpleNamespace(contexts=[existing], new_context=AsyncMock(return_value=fresh))
    chromium = SimpleNamespace(launch_persistent_context=AsyncMock(return_value=fresh),
                               connect_over_cdp=AsyncMock(return_value=browser))
    context, artifacts, _ = await browser_factory.BrowserContextFactory.create_browser_context(
        SimpleNamespace(chromium=chromium))
    if enterprise:
        assert context is fresh
        assert artifacts.har_path is None
        console.assert_not_called()
        launch = browser.new_context if browser_type == "cdp-connect" else chromium.launch_persistent_context
        launch.assert_awaited_once()
        assert launch.call_args.kwargs.get("record_video_dir") is None
        assert launch.call_args.kwargs.get("record_har_path") is None
    else:
        console.assert_called_once()
        if browser_type == "cdp-connect":
            assert context is existing
            browser.new_context.assert_not_awaited()
        else:
            assert chromium.launch_persistent_context.call_args.kwargs["record_video_dir"]
            assert chromium.launch_persistent_context.call_args.kwargs["record_har_path"]


@pytest.mark.parametrize("ensure_ascii", [True, False])
def test_unicode_credential_is_masked_after_json_serialization(monkeypatch, ensure_ascii):
    context = WorkflowRunContext("demo", "wf_demo", "wp_demo", "wfr_demo", None,
                                 SimpleNamespace(description=runtime.MARKER))
    context.secrets["placeholder_demo"] = 'synthetic-密码-🔒-"&'
    monkeypatch.setattr(runtime, "current_native_context", lambda: context)
    encoded = json.dumps({"value": context.secrets["placeholder_demo"]}, ensure_ascii=ensure_ascii)
    prompt, _ = runtime.safe_model_inputs(encoded, None, False)
    allowed, data, _ = runtime.safe_artifact_data(ArtifactType.VISIBLE_ELEMENTS_TREE, encoded.encode(), None)
    assert allowed
    assert json.loads(prompt) == json.loads(data) == {"value": "*****"}


@pytest.mark.parametrize("candidate", [{}, {"rows": None}, {"rows": [{}]}])
def test_native_table_filler_cannot_turn_missing_data_into_success(candidate):
    steps = [SkillStep("table_extract", {"headers": ["price"]})]
    native = compile_native_skills(steps, title="demo", url="http://controlled")
    filled = validate_and_fill_extraction_result(candidate, native.workflow_definition.blocks[0].data_schema)
    with pytest.raises(ValueError):
        compile_skill_pipeline(steps).validate_extracted_information(filled)


@pytest.mark.parametrize("candidate", [{"rows": []}, {"rows": [{"price": "12.50"}]}])
def test_native_table_preserves_valid_empty_and_populated_results(candidate):
    steps = [SkillStep("table_extract", {"headers": ["price"]})]
    compiled = compile_skill_pipeline(steps)
    filled = validate_and_fill_extraction_result(candidate, compiled.extracted_information_schema)
    assert compiled.validate_extracted_information(filled) == candidate
