"""Native credential placeholders and common model/Artifact boundaries; synthetic secrets only."""

import asyncio
import datetime
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from enterprise.workflows import runtime
from skyvern.forge.sdk.artifact.models import ArtifactType
from skyvern.forge.sdk.core import skyvern_context
from skyvern.forge.sdk.schemas.credentials import PasswordCredential
from skyvern.forge.sdk.workflow import context_manager
from skyvern.forge.sdk.workflow.models.parameter import CredentialParameter
from skyvern.webeye.actions import handler


@pytest.mark.asyncio
async def test_native_vault_values_are_placeholders_and_all_shared_outputs_are_masked(monkeypatch):
    workflow = SimpleNamespace(description=runtime.MARKER)
    ctx = context_manager.WorkflowRunContext("demo", "wf_demo", "wp_demo", "wfr_demo", None, workflow)
    credential = SimpleNamespace(vault_type="custom", totp_identifier=None)
    vault = AsyncMock(
        return_value=SimpleNamespace(
            credential=PasswordCredential(username="synthetic-private-user", password="synthetic-private-password")
        )
    )
    app = SimpleNamespace(
        DATABASE=SimpleNamespace(get_credential=AsyncMock(return_value=credential)),
        CREDENTIAL_VAULT_SERVICES={"custom": SimpleNamespace(get_credential_item=vault)},
        WORKFLOW_CONTEXT_MANAGER=SimpleNamespace(
            workflow_run_contexts={"wfr_demo": ctx}, get_workflow_run_context=lambda _run: ctx
        ),
    )
    monkeypatch.setattr(context_manager, "app", app)
    monkeypatch.setattr(runtime, "app", app)
    monkeypatch.setattr(handler, "app", app)
    binding = AsyncMock()
    monkeypatch.setattr(runtime, "check_credential_binding", binding)
    await ctx.register_credential_parameter_value(
        CredentialParameter(
            credential_parameter_id="cp_demo",
            workflow_id="wf_demo",
            key="portal",
            credential_id="cred_demo",
            created_at=datetime.datetime.now(datetime.UTC),
            modified_at=datetime.datetime.now(datetime.UTC),
        ),
        SimpleNamespace(organization_id="org_demo"),
    )
    assert binding.await_count == 1
    assert "synthetic-private" not in json.dumps(ctx.values)
    assert not await ctx._should_include_secrets_in_templates()
    skyvern_context.set(skyvern_context.SkyvernContext(workflow_run_id="wfr_demo"))
    try:
        prompt, images = runtime.safe_model_inputs(
            "DOM synthetic-private-password synthetic-private-user", [b"sensitive-pixels"], False
        )
        assert "synthetic-private" not in prompt and images is None
        import html

        escaped_secret = 'synthetic-escaped-"&password'
        ctx.secrets["encoded-demo"] = escaped_secret
        for encoded in (json.dumps(escaped_secret)[1:-1], html.escape(escaped_secret)):
            assert "synthetic-escaped" not in ctx.mask_secrets_in_data(encoded)
        with pytest.raises(ValueError, match="history"):
            runtime.safe_model_inputs("demo", None, True)
        for kind in (ArtifactType.SCREENSHOT_LLM, ArtifactType.HAR, ArtifactType.TRACE, ArtifactType.PDF):
            assert runtime.safe_artifact_data(kind, b"synthetic-private-password", None)[0] is False
        allowed, data, path = runtime.safe_artifact_data(
            ArtifactType.HTML_SCRAPE, b"<input value='synthetic-private-password'>", None
        )
        assert allowed and b"synthetic-private" not in data and path is None
        assert not runtime.safe_artifact_data(ArtifactType.HTML_SCRAPE, None, "not-read")[0]
        key = ctx.values["portal"]["password"]
        with pytest.raises(ValueError, match="controlled text input"):
            handler.get_actual_value_of_parameter_if_secret_with_task(SimpleNamespace(workflow_run_id="wfr_demo"), key)
        assert (
            handler.get_actual_value_of_parameter_if_secret_with_task(
                SimpleNamespace(workflow_run_id="wfr_demo"), key, allow_credential_input=True
            )
            == "synthetic-private-password"
        )
    finally:
        skyvern_context.reset()
    # Exercise the real ArtifactManager write path, not just its redaction helper.
    from skyvern.forge.sdk.artifact import manager as artifact_manager
    from skyvern.forge.sdk.db.models import ArtifactModel

    app.DATABASE.bulk_create_artifacts = AsyncMock(side_effect=lambda models: models)
    app.DATABASE.create_artifact = AsyncMock()
    app.STORAGE = SimpleNamespace(store_artifact=AsyncMock(), store_artifact_from_path=AsyncMock())
    monkeypatch.setattr(artifact_manager, "app", app)
    skyvern_context.set(skyvern_context.SkyvernContext(workflow_run_id="wfr_demo"))
    manager = artifact_manager.ArtifactManager()
    from skyvern.forge.sdk import forge_log

    rendered = forge_log.mask_enterprise_secrets(
        None, "error", {"event": "synthetic-private-password", "exception": "failure synthetic-private-user"}
    )
    assert "synthetic-private" not in json.dumps(rendered)
    try:
        request = artifact_manager.BulkArtifactCreationRequest(
            primary_key="stage4-secret-test",
            artifacts=[
                artifact_manager.ArtifactBatchData(
                    artifact_model=ArtifactModel(
                        artifact_id="art_safe",
                        organization_id="org_demo",
                        artifact_type="html_scrape",
                        uri="synthetic://evidence",
                    ),
                    data=b"synthetic-private-password",
                ),
                artifact_manager.ArtifactBatchData(
                    artifact_model=ArtifactModel(
                        artifact_id="art_visual",
                        organization_id="org_demo",
                        artifact_type="screenshot_llm",
                        uri="synthetic://omitted",
                    ),
                    data=b"pixels",
                ),
            ],
        )
        assert await manager._bulk_create_artifacts(request) == ["art_safe"]
        await asyncio.gather(*manager.upload_aiotasks_map.pop("stage4-secret-test"))
        assert app.STORAGE.store_artifact.call_args.args[1] == b"*****"
        assert (
            await manager._create_artifact(
                "stage4-secret-test",
                "art_visual",
                ArtifactType.SCREENSHOT_FINAL,
                "synthetic://omitted",
                "org_demo",
                data=b"pixels",
            )
            == ""
        )
        app.DATABASE.create_artifact.assert_not_awaited()
        app.DATABASE.get_artifact_by_id = AsyncMock()
        # Use native Artifact, whose item access is part of the update contract.
        from skyvern.forge.sdk.artifact.models import Artifact

        app.DATABASE.get_artifact_by_id.return_value = Artifact(
            artifact_id="art_safe", artifact_type=ArtifactType.HTML_SCRAPE,
            organization_id="org_demo", task_id="stage4-secret-test", uri="synthetic://evidence",
            created_at=datetime.datetime.now(datetime.UTC), modified_at=datetime.datetime.now(datetime.UTC),
        )
        await manager.update_artifact_data("art_safe", "org_demo", b"synthetic-private-password")
        await asyncio.gather(*manager.upload_aiotasks_map.pop("stage4-secret-test"))
        assert app.STORAGE.store_artifact.call_args.args[1] == b"*****"
    finally:
        skyvern_context.reset()
    vault.side_effect = RuntimeError("synthetic-private-password")
    with pytest.raises(ValueError, match="provider unavailable") as error:
        await ctx.register_credential_parameter_value(
            CredentialParameter(
                credential_parameter_id="cp_demo",
                workflow_id="wf_demo",
                key="portal",
                credential_id="cred_demo",
                created_at=datetime.datetime.now(datetime.UTC),
                modified_at=datetime.datetime.now(datetime.UTC),
            ),
            SimpleNamespace(organization_id="org_demo"),
        )
    assert "synthetic-private" not in str(error.value)


@pytest.mark.asyncio
async def test_enterprise_credential_fill_never_enters_autocomplete_or_leaks_browser_errors(monkeypatch):
    secret = "synthetic-private-password"
    context = SimpleNamespace(
        workflow=SimpleNamespace(description=runtime.MARKER),
        get_original_secret_value_or_none=lambda value: secret if value == "placeholder" else None,
    )
    element = SimpleNamespace(
        get_frame=lambda: SimpleNamespace(url="http://controlled"), get_tag_name=lambda: "input", get_locator=lambda: None,
        input_fill=AsyncMock(side_effect=RuntimeError(secret)),
    )
    monkeypatch.setattr(handler, "app", SimpleNamespace(
        WORKFLOW_CONTEXT_MANAGER=SimpleNamespace(get_workflow_run_context=lambda _run: context)
    ))
    monkeypatch.setattr(handler, "DomUtil", lambda *_args: SimpleNamespace(get_skyvern_element_by_id=AsyncMock(return_value=element)))
    monkeypatch.setattr(handler.SkyvernFrame, "create_instance", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(handler, "IncrementalScrapePage", lambda **_kwargs: None)
    monkeypatch.setattr(handler, "get_input_value", AsyncMock(return_value=""))
    check = AsyncMock()
    monkeypatch.setattr(runtime, "check_secret_input", check)
    action = SimpleNamespace(element_id="password-input", text="placeholder", totp_timing_info=None)
    result = await handler.handle_input_text_action(
        action, SimpleNamespace(url="http://controlled"),
        SimpleNamespace(id_to_element_dict={"password-input": {"tagName": "input"}}),
        SimpleNamespace(workflow_run_id="wfr_demo"), None,
    )
    check.assert_awaited_once_with(context, "http://controlled", frame_url="http://controlled")
    element.input_fill.assert_awaited_once_with(text=secret)
    assert "synthetic-private" not in str(result)
    element.input_fill.side_effect = None
    assert (await handler.handle_input_text_action(
        action, SimpleNamespace(url="http://controlled"),
        SimpleNamespace(id_to_element_dict={"password-input": {"tagName": "input"}}),
        SimpleNamespace(workflow_run_id="wfr_demo"), None,
    ))[0].success
