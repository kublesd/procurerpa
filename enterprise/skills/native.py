"""Skill compilation into native Workflow blocks; no independent browser executor."""

import json

from enterprise.skills.base import get_skill
from enterprise.skills.executor import SkillStep, _safe_value, compile_skill_pipeline
from skyvern.forge.sdk.workflow.models.parameter import WorkflowParameterType
from skyvern.schemas.workflows import (
    CredentialParameterYAML,
    ExtractionBlockYAML,
    FileDownloadBlockYAML,
    LoginBlockYAML,
    NavigationBlockYAML,
    WorkflowCreateYAMLRequest,
    WorkflowDefinitionYAML,
    WorkflowParameterYAML,
)


def compile_native_skills(
    steps: list[SkillStep], *, title: str, url: str, credential_id: str | None = None
) -> WorkflowCreateYAMLRequest:
    """Compile declared Skills; only native credential references cross authentication boundaries."""
    if not steps or len(steps) > 32:
        raise ValueError("Invalid native Skill sequence")
    blocks = []
    parameters = []
    for index, step in enumerate(steps):
        if step.error_strategy_override not in (None, "abort"):
            raise ValueError("Unsupported native Skill failure strategy")
        if step.skill_name in ("login", "session_keep_alive"):
            import re

            if not credential_id or not re.fullmatch(r"cred_[A-Za-z0-9_]{1,120}", credential_id):
                raise ValueError("Skill credentials/session authentication are not_connected")
            allowed = {"url", "credential_id"} if step.skill_name == "login" else {"session_timeout_indicator"}
            if set(step.params) - allowed or step.params.get("credential_id", credential_id) != credential_id:
                raise ValueError("Unsafe native credential input")
            if step.params.get("url", url) != url:
                raise ValueError("Unsafe native credential URL")
            if not any(p.key == "portal_credential" for p in parameters):
                parameters.append(CredentialParameterYAML(key="portal_credential", credential_id=credential_id))
            blocks.append(
                LoginBlockYAML(
                    label=f"{step.skill_name}_{index}",
                    url=url if index == 0 else None,
                    navigation_goal="Authenticate on the controlled portal if the session is expired, using the credential placeholders. Do not submit procurement decisions.",
                    parameter_keys=["portal_credential"],
                    disable_cache=True,
                    max_retries=0,
                    max_steps_per_run=30,
                )
            )
            continue
        skill = get_skill(step.skill_name)
        if skill is None or step.error_strategy_override not in (None, "abort"):
            raise ValueError("Unsupported native Skill or failure strategy")
        if set(step.params) - set(skill.params_model.model_fields) or _safe_value(step.params) != step.params:
            raise ValueError("Unsafe native Skill input")
        try:
            params = skill().validate_params(step.params).model_dump(mode="json")
        except ValueError:
            raise ValueError("Invalid native Skill input") from None
        label = f"{step.skill_name}_{index}"
        fields = dict(label=label, url=url if index == 0 else None, max_retries=0, disable_cache=True)
        if step.skill_name == "table_extract":
            compiled = compile_skill_pipeline([step])
            block = ExtractionBlockYAML(
                **fields,
                data_extraction_goal=compiled.data_extraction_goal,
                data_schema=compiled.extracted_information_schema,
            )
        elif step.skill_name == "file_download":
            key = f"inputs_{index}"
            parameters.append(
                WorkflowParameterYAML(
                    key=key,
                    workflow_parameter_type=WorkflowParameterType.JSON,
                    default_value={"trigger_text": params.get("trigger_text")},
                )
            )
            block = FileDownloadBlockYAML(
                **fields,
                navigation_goal="Download the requested attachment using the supplied trigger. Retain native download evidence.",
                parameter_keys=[key],
            )
        elif step.skill_name in ("form_fill", "search_and_select", "pagination"):
            compiled = compile_skill_pipeline([step])
            payload = compiled.navigation_payload
            key = f"inputs_{index}"
            parameters.append(
                WorkflowParameterYAML(
                    key=key,
                    workflow_parameter_type=WorkflowParameterType.JSON,
                    default_value=json.loads(json.dumps(payload)),
                )
            )
            goal = compiled.navigation_goal
            block = NavigationBlockYAML(**fields, navigation_goal=goal, parameter_keys=[key], max_steps_per_run=50)
        else:
            raise ValueError("Unsupported native Skill")
        blocks.append(block)
    return WorkflowCreateYAMLRequest(
        title=title,
        description="enterprise-skill/v1",
        run_with="agent",
        ai_fallback=False,
        adaptive_caching=False,
        generate_script_on_terminal=False,
        persist_browser_session=False,
        workflow_definition=WorkflowDefinitionYAML(parameters=parameters, blocks=blocks),
    )
