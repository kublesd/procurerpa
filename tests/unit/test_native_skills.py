import pytest

from enterprise.skills.executor import SkillStep
from enterprise.skills.native import compile_native_skills


def test_public_skills_map_to_distinct_native_blocks_and_evidence_boundaries():
    steps = [
        SkillStep("form_fill", {"field_mapping": {"物料": "demo-material"}}),
        SkillStep("search_and_select", {"search_text": "demo", "target_text": "demo"}),
        SkillStep("pagination", {"max_pages": 2}),
        SkillStep("table_extract", {"headers": ["物料"]}),
        SkillStep("file_download", {"download_path": "./demo", "trigger_text": "导出"}),
    ]
    workflow = compile_native_skills(steps, title="controlled-demo", url="http://localhost:18080/demo")
    blocks = workflow.workflow_definition.blocks
    assert [block.block_type.value for block in blocks] == [
        "navigation",
        "navigation",
        "navigation",
        "extraction",
        "file_download",
    ]
    assert [block.label for block in blocks] == [f"{step.skill_name}_{i}" for i, step in enumerate(steps)]
    assert all(block.disable_cache and not block.continue_on_failure for block in blocks)
    assert blocks[0].url and all(block.url is None for block in blocks[1:])
    assert "./demo" not in workflow.model_dump_json()
    assert not workflow.persist_browser_session
    assert blocks[3].data_schema["required"] == ["rows"]


@pytest.mark.parametrize("name", ["login", "session_keep_alive"])
def test_credential_policy_pending_fails_closed(name):
    with pytest.raises(ValueError, match="not_connected"):
        compile_native_skills([SkillStep(name, {})], title="demo", url="http://localhost")


@pytest.mark.parametrize(
    "step",
    [
        SkillStep("form_fill", {"field_mapping": {"password": "synthetic-secret"}}),
        SkillStep("search_and_select", {"search_text": "demo", "target_text": "demo", "token": "synthetic-secret"}),
        SkillStep("pagination", {"max_pages": "synthetic-secret"}),
        SkillStep("form_fill", {"field_mapping": {}}, error_strategy_override="skip"),
    ],
)
def test_native_compiler_rejects_unsafe_or_invalid_inputs_without_echo(step):
    with pytest.raises(ValueError) as error:
        compile_native_skills([step], title="demo", url="http://localhost")
    assert "synthetic-secret" not in str(error.value)


def test_all_six_templates_use_native_credential_references_and_distinct_blocks():
    from enterprise.workflows.templates import TEMPLATE_REGISTRY, compile_native_template
    from skyvern.forge.sdk.workflow.workflow_definition_converter import convert_workflow_definition

    for template in TEMPLATE_REGISTRY.values():
        params = {
            p.name: "http://localhost:18080/portal"
            if p.param_type.value == "url"
            else "cred_demo"
            if p.name == "credential_id"
            else "2026-01-01"
            if p.param_type.value == "date"
            else "1"
            if p.param_type.value == "integer"
            else "synthetic"
            for p in template.parameters
            if p.required
        }
        compiled = compile_native_template(template, params)
        definition = convert_workflow_definition(compiled.workflow_definition, "wf_demo")
        assert len(definition.blocks) == len(template.skill_steps)
        assert all(
            block.max_retries == 0 and not block.continue_on_failure and block.disable_cache
            for block in definition.blocks
        )
        assert next(p for p in definition.parameters if p.key == "portal_credential").credential_id == "cred_demo"
        assert not {"username", "password"} & {p.name for p in template.parameters}
        assert compiled.description == "enterprise-skill/v1"


def test_session_checks_share_native_login_and_reject_inline_secrets():
    steps = [SkillStep("login", {"credential_id": "cred_demo"}), SkillStep("session_keep_alive", {})]
    compiled = compile_native_skills(steps, title="demo", url="http://localhost", credential_id="cred_demo")
    assert [block.label for block in compiled.workflow_definition.blocks] == ["login_0", "session_keep_alive_1"]
    assert len(compiled.workflow_definition.parameters) == 1
    with pytest.raises(ValueError, match="Unsafe native credential input"):
        compile_native_skills(
            [SkillStep("login", {"password": "synthetic-secret"})],
            title="demo",
            url="http://localhost",
            credential_id="cred_demo",
        )
