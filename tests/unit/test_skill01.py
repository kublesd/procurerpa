"""Credential-free native quote template boundary checks."""
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from enterprise.auth.dependencies import get_current_user
from enterprise.workflows import routes
from tests.unit.test_day_11_quotes import _payload, _user


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = _user
    with TestClient(app) as value:
        yield value


@pytest.mark.parametrize("outcome,status,approval", [
    ("completed", "completed", None), ("pending_approval", "created", "approval_a"),
])
def test_template_delegates_same_context_and_idempotency(client, monkeypatch, outcome, status, approval):
    boundary = AsyncMock(return_value=routes.procurement_routes.QuoteTaskResponse(
        task_id="task_a", task_status=status, outcome=outcome, idempotent=False,
        approval_id=approval, quote_id="quote_a" if approval is None else None,
        artifact_id="artifact_a" if approval is None else None,
    ))
    monkeypatch.setattr(routes.procurement_routes, "quote_task", boundary)
    response = client.post(
        "/enterprise/workflows/instantiate/quote-task/v1",
        json=_payload().model_dump(mode="json"), headers={"Idempotency-Key": "synthetic-key"},
    )
    assert response.status_code == 200
    assert response.json()["template_id"] == "quote-task/v1"
    assert response.json()["execution_mode"] == "real"
    assert response.json()["outcome"] == outcome
    assert response.json()["approval_id"] == approval
    kwargs = boundary.await_args.kwargs
    assert kwargs["payload"] == _payload()
    assert kwargs["user"] == _user()
    assert kwargs["idempotency_key"] == "synthetic-key"


def test_template_requires_idempotency_before_dispatch(client, monkeypatch):
    boundary = AsyncMock()
    monkeypatch.setattr(routes.procurement_routes, "quote_task", boundary)
    response = client.post("/enterprise/workflows/instantiate/quote-task/v1", json=_payload().model_dump(mode="json"))
    assert response.status_code == 422
    boundary.assert_not_awaited()


def test_cross_organization_rejected_by_actual_procurement_boundary(client, monkeypatch):
    monkeypatch.setattr(routes.procurement_routes.settings, "ENV", "local")
    creator = AsyncMock()
    monkeypatch.setattr(routes.procurement_routes, "_create_smoke_task", creator)
    body = _payload().model_dump(mode="json")
    body["organization_id"] = "org_other"
    response = client.post(
        "/enterprise/workflows/instantiate/quote-task/v1", json=body,
        headers={"Idempotency-Key": "synthetic-key"},
    )
    assert response.status_code == 403
    creator.assert_not_awaited()


@pytest.mark.parametrize("case,expected", [("production", 404), ("url", 400), ("department", 403)])
def test_template_keeps_actual_environment_url_and_scope_guards(client, monkeypatch, case, expected):
    monkeypatch.setattr(routes.procurement_routes.settings, "ENV", "prod" if case == "production" else "local")
    monkeypatch.setattr(routes.procurement_routes, "_allowed_smoke_urls", lambda: {_payload().url})
    creator = AsyncMock()
    monkeypatch.setattr(routes.procurement_routes, "_create_smoke_task", creator)
    body = _payload().model_dump(mode="json")
    if case == "url":
        body["url"] = "https://outside.example/quote"
    elif case == "department":
        body["department_id"] = "dept_other"
    response = client.post(
        "/enterprise/workflows/instantiate/quote-task/v1", json=body,
        headers={"Idempotency-Key": "synthetic-key"},
    )
    assert response.status_code == expected
    creator.assert_not_awaited()
