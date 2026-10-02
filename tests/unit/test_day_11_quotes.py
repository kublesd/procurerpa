import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from starlette.requests import Request

from enterprise.auth.schemas import DepartmentRole, UserContext
from enterprise.procurement import routes
from skyvern.forge.sdk.schemas.tasks import TaskStatus


def _payload() -> routes.QuoteTaskRequest:
    return routes.QuoteTaskRequest(
        organization_id="org_a",
        department_id="dept_a",
        category_id="pc_a",
        url="https://supplier.example/quote",
    )


def _user() -> UserContext:
    return UserContext(
        user_id="user_a",
        org_id="org_a",
        department_roles=[DepartmentRole(department_id="dept_a", department_name="A", role="operator")],
        business_line_ids=[],
        procurement_category_ids=["pc_a"],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapped,price,expected", [
    (False, "10.005", "10.01"), (True, "10.005", "10.01"), (True, "1.0049999999999999999", "1.00"),
])
async def test_extracted_quote_is_validated_before_persistence(monkeypatch, wrapped, price, expected) -> None:
    added = []
    monkeypatch.setattr(routes, "advance_quote_state", AsyncMock())
    monkeypatch.setattr(routes, "write_audit_log", AsyncMock())

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def scalar(self, statement):
            sql = str(statement)
            if "supplier_quotes" in sql:
                return None
            if "task_extensions" in sql:
                return SimpleNamespace(task_id="task_a")
            return "artifact_a"

        def add(self, model):
            added.append(model)

        async def commit(self):
            pass

    monkeypatch.setattr(
        routes,
        "forge_app",
        SimpleNamespace(DATABASE=SimpleNamespace(Session=lambda: Session())),
    )
    task = SimpleNamespace(
        task_id="task_a",
        status=TaskStatus.completed,
        extracted_information={
            "supplier_id": "supplier-a",
            "material_name": "SSD",
            "quantity": "10",
            "unit": " UNIT \t",
            "currency": " cNy\n",
            "unit_price_cny": price,
            "freight_cny": "1.005",
            "moq": "1",
            "delivery_days": 5,
            "confidence": "0.95",
        },
    )

    original = task.extracted_information.copy()
    if wrapped:
        task.extracted_information = "```json\n" + json.dumps(original).replace(f'"{price}"', price) + "\n```"
    original_information = task.extracted_information
    quote = await routes._persist_extracted_quote(task, _payload(), _user())
    assert quote.task_id == "task_a"
    assert quote.artifact_id == "artifact_a"
    assert quote.unit_price_cny == Decimal(expected)
    assert (quote.unit, quote.currency) == ("unit", "CNY")
    assert task.extracted_information == original_information
    assert len(added) == 1

    task.extracted_information = {**original, "confidence": "0.20"}
    with pytest.raises(HTTPException) as error:
        await routes._persist_extracted_quote(task, _payload(), _user())
    assert error.value.status_code == 422
    assert error.value.detail["code"] == "quote_needs_human_confirmation"
    assert len(added) == 2
    assert added[-1].status == "pending"


@pytest.mark.asyncio
async def test_quote_task_uses_native_extraction_request(monkeypatch) -> None:
    monkeypatch.setattr(routes, "review_risk", AsyncMock(return_value={"risk_level": "low"}))
    user = _user()
    payload = _payload()
    completed = SimpleNamespace(task_id="task_a", status=TaskStatus.completed)
    created_requests = []

    async def create_task(**kwargs):
        assert kwargs["defer_execution"] is True
        created_requests.append(kwargs["task_request"])
        return SimpleNamespace(task_id="task_a", status=TaskStatus.created)

    async def attach(*_args):
        return None

    async def get_task(*_args):
        return completed

    async def persist(*_args):
        return SimpleNamespace(quote_id="sq_a", artifact_id="artifact_a")

    async def validate(*_args):
        pass

    monkeypatch.setattr(routes.settings, "ENV", "local")
    monkeypatch.setattr(routes, "_allowed_smoke_urls", lambda: {payload.url})
    monkeypatch.setattr(routes, "_validate_smoke_context", validate)
    monkeypatch.setattr(routes, "_persisted_request", AsyncMock(return_value=None))
    monkeypatch.setattr(routes, "_create_smoke_task", create_task)
    monkeypatch.setattr(routes, "_attach_procurement_context", attach)
    monkeypatch.setattr(routes, "_get_smoke_task", get_task)
    monkeypatch.setattr(routes, "_persist_extracted_quote", persist)
    recovered = AsyncMock(return_value=SimpleNamespace(quote_id="sq_a", artifact_id="artifact_a"))
    monkeypatch.setattr(routes, "recover_quote_task", recovered)
    request = Request({"type": "http", "method": "POST", "path": "/quote-task", "headers": []})
    result = await routes.quote_task(payload, request, Response(), BackgroundTasks(), "key-a", user)

    assert result.outcome == "completed"
    assert result.quote_id == "sq_a"
    recovered.assert_awaited_once_with("task_a", user)
    assert created_requests[0].data_extraction_goal == routes._QUOTE_EXTRACTION_GOAL
    assert created_requests[0].extracted_information_schema == routes.QUOTE_EXTRACTION_SCHEMA


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [
    {"unit": "box"}, {"unit": "units"}, {"currency": "USD"}, {"currency": "RMB"},
    {"currency": "人民币"}, {"unit": None}, {"currency": 1}, {"unit_price_cny": "NaN"},
    {"unit_price_cny": "-1"}, {"quantity": "0"}, {"freight_cny": "Infinity"},
    {"unexpected": "synthetic-private-marker"}, "[]", "```json\n{broken\n```", "null",
])
async def test_invalid_extraction_reaches_safe_review(monkeypatch, invalid):
    from tests.unit.test_s1_human_reviews import _Database, _task

    database = _Database()
    monkeypatch.setattr(routes, "forge_app", SimpleNamespace(DATABASE=database))
    monkeypatch.setattr(routes, "advance_quote_state", AsyncMock())
    monkeypatch.setattr(routes, "write_audit_log", AsyncMock())
    task = _task()
    task.extracted_information = (
        {**task.extracted_information, "confidence": "0.95", **invalid} if isinstance(invalid, dict) else invalid
    )
    with pytest.raises(HTTPException) as error:
        await routes._persist_extracted_quote(task, _payload(), _user())
    assert error.value.detail["reason_code"] == "quote_schema_invalid"
    assert "synthetic-private-marker" not in str(error.value.detail)
    assert error.value.__suppress_context__
    assert database.quote is None and database.review.status == "pending"


@pytest.mark.parametrize("missing", ["quantity", "unit_price_cny", "freight_cny", "moq", "delivery_days"])
def test_native_schema_preserves_missing_quote_numbers(missing):
    from pydantic import ValidationError

    from skyvern.forge.sdk.api.llm.schema_validator import validate_and_fill_extraction_result
    from tests.unit.test_s1_human_reviews import _task

    data = _task().extracted_information
    del data[missing]
    result = validate_and_fill_extraction_result(data, routes.QUOTE_EXTRACTION_SCHEMA)
    assert missing not in result
    with pytest.raises(ValidationError):
        routes.ExtractedSupplierQuote.model_validate(result)


def test_native_markdown_parser_feeds_quote_validator():
    from skyvern.forge.sdk.api.llm.utils import parse_api_response
    from tests.unit.test_s1_human_reviews import _task

    raw = "```json\n" + json.dumps(_task().extracted_information) + "\n```"
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=raw))])
    parsed = parse_api_response(response, force_dict=False)
    assert routes.ExtractedSupplierQuote.model_validate(parsed).unit_price_cny == Decimal("10.00")


def test_non_quote_native_schema_keeps_existing_defaults():
    from skyvern.forge.sdk.api.llm.schema_validator import validate_and_fill_extraction_result

    schema = {"type": "object", "properties": {"count": {"type": "integer"}}, "required": ["count"]}
    assert validate_and_fill_extraction_result({}, schema) == {"count": 0}


@pytest.mark.asyncio
async def test_legacy_quote_schema_still_recovers_context(monkeypatch):
    from tests.unit.test_approval_routes import _user as recovery_user
    from tests.unit.test_procurement_review_regressions import _install_recovery

    task, _ = _install_recovery(monkeypatch)
    task.extracted_information_schema = {
        key: value for key, value in routes.QUOTE_EXTRACTION_SCHEMA.items() if key != "x-skyvern-preserve-missing"
    }
    assert await routes.quote_continuation_payload(task, recovery_user("buyer", "operator")) is not None
    task.extracted_information_schema = {"type": "object"}
    assert await routes.quote_continuation_payload(task, recovery_user("buyer", "operator")) is None
