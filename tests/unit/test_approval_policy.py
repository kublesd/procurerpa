"""Frozen approval policy boundaries and failure-closed routing."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from enterprise.approval.policy import POLICY_VERSION, policy_snapshot, resolve_approval_route
from enterprise.approval.routes import DecisionRequest, _user_can_approve
from enterprise.procurement.routes import ProcurementRiskInput, SmokeTaskRequest
from tests.unit.test_approval_routes import _approval, _user


@pytest.mark.parametrize("amount,threshold", [
    ("49999.99", None), ("50000", "50000"), ("99999.99", "50000"),
    ("100000", "100000"), ("999999.99", "100000"), ("1000000", "1000000"),
])
def test_exact_snapshot_threshold(amount, threshold):
    snapshot = policy_snapshot(Decimal(amount))
    assert snapshot["matched_threshold_cny"] == (Decimal(threshold) if threshold else None)
    assert snapshot["total_amount_cny"] == Decimal(amount)
    assert snapshot["currency"] == "CNY" and snapshot["policy_version"] == POLICY_VERSION


@pytest.mark.asyncio
@pytest.mark.parametrize("departments,approver", [([], "u"), (["a", "b"], "u"), (["a"], None)])
async def test_critical_missing_duplicate_or_unstaffed_compliance_fails_closed(departments, approver):
    session = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: departments)),
                              scalar=AsyncMock(return_value=approver))
    with pytest.raises(HTTPException) as denied:
        await resolve_approval_route(session, org_id="o", department_id="source", category_id="cat",
                                     requester_user_id="requester", risk_level="critical")
    assert denied.value.status_code == 422


@pytest.mark.parametrize("field", ["policy_version", "policy_effective_at", "matched_threshold_cny",
                                   "approver_department_id", "approver_role", "currency"])
def test_client_cannot_write_server_policy(field):
    for model, values in (
        (SmokeTaskRequest, dict(organization_id="o", department_id="d", category_id="c", url="https://example.test")),
        (ProcurementRiskInput, {}), (DecisionRequest, {}),
    ):
        with pytest.raises(ValidationError):
            model(**values, **{field: "client-controlled"})


def test_versioned_snapshot_enforces_all_dimensions_and_self_approval():
    approval = _approval(policy_version=POLICY_VERSION, category_id="cat_1", approver_role="approver")
    assert _user_can_approve(_user("approver", "approver"), approval, "different-task-extension-category")
    for user in (_user("buyer_1", "approver"), _user("u", "approver", org_id="other"),
                 _user("u", "approver", department_id="other"), _user("u", "org_admin"),
                 _user("u", "approver").model_copy(update={"procurement_category_ids": []})):
        assert not _user_can_approve(user, approval)


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1"])
def test_nonfinite_or_negative_amount_rejected(amount):
    with pytest.raises(ValidationError):
        ProcurementRiskInput(total_amount_cny=amount)
