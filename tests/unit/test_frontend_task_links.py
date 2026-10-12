"""Authorized read-only task associations; no external services."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from enterprise.auth.schemas import DepartmentRole, UserContext
from enterprise.procurement import routes


@pytest.mark.asyncio
@pytest.mark.parametrize("role,requester,expected", [
    ("operator", "user-demo", "apr-demo"),
    ("operator", "someone-else", None),
    ("approver", "someone-else", "apr-demo"),
    ("viewer", "someone-else", None),
])
async def test_task_associations_reuse_approval_and_review_visibility(monkeypatch, role, requester, expected):
    user = UserContext(user_id="user-demo", org_id="org-demo",
        department_roles=[DepartmentRole(department_id="dept-demo", department_name="Demo", role=role)],
        procurement_category_ids=["cat-demo"])
    monkeypatch.setattr(routes, "get_procurement_task", AsyncMock(return_value={
        "task_id": "task-demo", "category_id": "cat-demo",
    }))
    approval = SimpleNamespace(approval_id="apr-demo", organization_id="org-demo",
        requester_user_id=requester, category_id="cat-demo", policy_version=None,
        approver_department_id="dept-demo")

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def scalars(self, statement):
            sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
            assert "org-demo" in sql and "task-demo" in sql
            return SimpleNamespace(all=lambda: [approval])

        async def scalar(self, statement):
            sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
            assert all(value in sql for value in ("org-demo", "task-demo", "dept-demo", "cat-demo"))
            return SimpleNamespace(review_id="review-demo")

    monkeypatch.setattr(routes, "forge_app", SimpleNamespace(DATABASE=SimpleNamespace(Session=Session)))
    result = await routes.procurement_task_detail("task-demo", user)
    assert result["approval_id"] == expected
    assert result["review_id"] == ("review-demo" if role == "operator" else None)


@pytest.mark.asyncio
async def test_invisible_task_does_not_query_associations(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(routes, "get_procurement_task", AsyncMock(side_effect=HTTPException(404)))
    monkeypatch.setattr(routes, "forge_app", None)
    with pytest.raises(HTTPException) as error:
        await routes.procurement_task_detail("outside-org", None)
    assert error.value.status_code == 404
