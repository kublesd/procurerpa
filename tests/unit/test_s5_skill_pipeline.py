"""S5 native Skill Pipeline compilation and execution checks."""

import json
from types import SimpleNamespace

import pytest

from enterprise.agent.skyvern_handler import SkyvernProcurementHandler
from enterprise.audit.models import AuditLogModel
from enterprise.auth.models import TaskExtensionModel
from enterprise.procurement.models import ProcurementHumanReviewModel
from enterprise.skills.executor import SkillStep, compile_skill_pipeline
from enterprise.workflows.templates import (
    SUPPLIER_QUOTE_LEDGER,
    TEMPLATE_REGISTRY,
    build_skill_pipeline,
    compile_template_pipeline,
)
from skyvern.forge.sdk.artifact.models import ArtifactType
from skyvern.forge.sdk.schemas.tasks import TaskStatus

URL = "https://supplier.example/quotes"
PARAMETERS = {
    "supplier_portal_url": URL,
    "credential_id": "cred_demo",
    "supplier_code": "SUP-001",
    "material_code": "MAT-001",
    "start_date": "2026-01-01",
    "end_date": "2026-03-01",
}


class Session:
    def __init__(self, database):
        self.database = database

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def add(self, row):
        self.database.rows.append(row)

    async def commit(self):
        return None


class Database:
    def __init__(self, extracted_information):
        self.rows = []
        self.task = SimpleNamespace(
            task_id="tsk_pipeline",
            status=TaskStatus.completed,
            url=URL,
            extracted_information=extracted_information,
        )
        self.artifact = SimpleNamespace(
            artifact_id="art_pipeline",
            artifact_type=ArtifactType.SCREENSHOT_FINAL,
            task_id=self.task.task_id,
            organization_id="org_a",
        )

    def Session(self):
        return Session(self)

    async def get_organization(self, organization_id):
        return SimpleNamespace(organization_id=organization_id)

    async def get_task(self, task_id, organization_id):
        if task_id == self.task.task_id and organization_id == "org_a":
            return self.task
        return None

    async def get_latest_artifact(self, **_kwargs):
        return self.artifact


def make_handler(database, calls):
    async def run_task(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(task_id=database.task.task_id)

    return SkyvernProcurementHandler(
        database=database,
        task_runner=run_task,
        organization_id="org_a",
        department_id="dept_a",
        category_id="cat_a",
        user_id="user_a",
        url=URL,
        allowed_urls={URL},
        compiled_pipeline=compile_skill_pipeline([
            step for step in build_skill_pipeline(SUPPLIER_QUOTE_LEDGER, PARAMETERS)
            if step.skill_name == "table_extract"
        ]),
    )


def valid_rows():
    return {
        "rows": [{
            "供应商编码": "SUP-001",
            "物料编码": "MAT-001",
            "含税单价": 12.34,
            "交期": "2026-03-10",
            "MOQ": 10,
        }],
    }


def test_login_template_cannot_compile_without_credential_connection():
    with pytest.raises(ValueError, match="not_connected"):
        compile_template_pipeline(SUPPLIER_QUOTE_LEDGER, PARAMETERS)


@pytest.mark.parametrize("template", TEMPLATE_REGISTRY.values(), ids=TEMPLATE_REGISTRY.keys())
def test_each_legacy_template_uses_same_closed_auth_contract(template):
    values = {
        p.name: "https://supplier.example/quote" if p.param_type.value == "url"
        else "2026-01-01" if p.param_type.value == "date"
        else "1" if p.param_type.value == "integer"
        else "synthetic"
        for p in template.parameters if p.required
    }
    with pytest.raises(ValueError, match="not_connected"):
        compile_template_pipeline(template, values)


def test_public_extraction_compiles_without_a_second_browser_runtime():
    compiled = compile_skill_pipeline([
        SkillStep(skill_name="table_extract", params={"headers": ["物料"]}),
        SkillStep(skill_name="pagination", params={"max_pages": 2}),
    ])
    assert "Traverse the requested result pages" in compiled.navigation_goal
    assert compiled.extracted_information_schema["properties"]["rows"]["type"] == "array"
    assert "https://" not in json.dumps(compiled.model_dump(mode="json"))


@pytest.mark.parametrize("name", ["login", "session_keep_alive"])
def test_authentication_steps_fail_closed(name):
    with pytest.raises(ValueError, match="not_connected"):
        compile_skill_pipeline([SkillStep(skill_name=name, params={})])


@pytest.fixture(autouse=True)
def controlled_routing(monkeypatch):
    from enterprise.agent import skyvern_handler
    from enterprise.llm.model_router import ProcurementPageKind, route_procurement_page
    routing = route_procurement_page(ProcurementPageKind.DYNAMIC_QUOTE_PORTAL)
    routing.resolved_model_key = "SKILL01_TEST"
    monkeypatch.setattr(skyvern_handler, "resolve_procurement_page", lambda _kind: routing)


@pytest.mark.asyncio
async def test_native_handler_runs_compiled_task_and_binds_structured_result_to_artifact():
    database, calls = Database(valid_rows()), []

    result = await make_handler(database, calls)("ignored", {})

    request = calls[0]["task"]
    assert request.data_extraction_goal
    assert request.extracted_information_schema
    assert calls[0]["defer_execution"] is False
    assert result["success"] is True
    assert result["artifact_id"] == "art_pipeline"
    assert result["data"]["extracted_information"] == valid_rows()
    assert any(isinstance(row, TaskExtensionModel) for row in database.rows)
    assert any(isinstance(row, AuditLogModel) for row in database.rows)


@pytest.mark.asyncio
async def test_invalid_table_result_fails_closed_into_human_review():
    database, calls = Database({"rows": [{"供应商编码": "SUP-001"}]}), []

    result = await make_handler(database, calls)("ignored", {})

    assert result["success"] is False
    assert result["error"] == "skill_table_schema_invalid"
    assert any(
        isinstance(row, ProcurementHumanReviewModel)
        and row.reason_code == "skill_table_schema_invalid"
        and row.artifact_id == "art_pipeline"
        for row in database.rows
    )
