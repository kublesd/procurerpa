"""Tests for procurement workflow templates, crypto, validation, and API.

Covers:
- 6 templates correctly registered
- Template query by industry
- Parameter validation (required, type, date range)
- Sensitive parameter encryption/decryption/masking
- API: list, detail, instantiate with validation and encryption
"""

import unittest
from unittest.mock import AsyncMock, patch

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from enterprise.workflows.crypto import (
    decrypt_value,
    encrypt_value,
    mask_value,
    reset_key,
    set_key,
)
from enterprise.workflows.templates import (
    PURCHASE_ORDER_DUE,
    SUPPLIER_QUOTE_LEDGER,
    TEMPLATE_REGISTRY,
    get_template,
    get_templates_by_industry,
)
from enterprise.workflows.validator import (
    validate_parameters,
)

# ============================================================
# Template Registry tests
# ============================================================

class TestTemplateRegistry(unittest.TestCase):
    def test_six_templates_registered(self):
        assert len(TEMPLATE_REGISTRY) == 6

    def test_all_template_ids_unique(self):
        ids = list(TEMPLATE_REGISTRY.keys())
        assert len(ids) == len(set(ids))

    def test_direct_material_templates(self):
        direct_materials = get_templates_by_industry("direct_materials")
        assert len(direct_materials) == 2
        names = {t.name for t in direct_materials}
        assert "供应商历史报价台账采集" in names
        assert "物料历史基准价采集" in names

    def test_mro_templates(self):
        mro = get_templates_by_industry("mro")
        assert len(mro) == 2
        names = {t.name for t in mro}
        assert "采购订单到期与催交清单" in names
        assert "供应商资质与报价附件批量归档" in names

    def test_services_templates(self):
        services = get_templates_by_industry("services")
        assert len(services) == 2
        names = {t.name for t in services}
        assert "询价单与采购任务批量状态查询" in names
        assert "供应商合同到期与续签核查" in names

    def test_get_template_by_id(self):
        t = get_template("tpl_supplier_quote_ledger")
        assert t is not None
        assert t.name == "供应商历史报价台账采集"

    def test_get_template_not_found(self):
        assert get_template("tpl_nonexistent") is None

    def test_each_template_has_parameters(self):
        for tid, t in TEMPLATE_REGISTRY.items():
            assert len(t.parameters) > 0, f"Template {tid} has no parameters"

    def test_each_template_has_sensitive_param(self):
        """Each template should have at least one sensitive parameter (password)."""
        for tid, t in TEMPLATE_REGISTRY.items():
            sensitive = [p for p in t.parameters if p.sensitive]
            assert len(sensitive) >= 1, f"Template {tid} has no sensitive parameters"

    def test_template_industries(self):
        industries = {t.industry.value for t in TEMPLATE_REGISTRY.values()}
        assert industries == {"direct_materials", "mro", "services"}


# ============================================================
# Crypto tests
# ============================================================

class TestCrypto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_key = Fernet.generate_key()
        set_key(cls.test_key)

    @classmethod
    def tearDownClass(cls):
        reset_key()

    def test_encrypt_decrypt_roundtrip(self):
        original = "MySecretPassword123!"
        encrypted = encrypt_value(original)
        decrypted = decrypt_value(encrypted)
        assert decrypted == original

    def test_encrypted_differs_from_plaintext(self):
        original = "password"
        encrypted = encrypt_value(original)
        assert encrypted != original

    def test_different_encryptions_differ(self):
        e1 = encrypt_value("same")
        e2 = encrypt_value("same")
        # Fernet uses random IV, so encryptions differ
        assert e1 != e2

    def test_decrypt_with_wrong_key_fails(self):
        encrypted = encrypt_value("secret")
        # Set a different key
        other_key = Fernet.generate_key()
        set_key(other_key)
        from cryptography.fernet import InvalidToken
        with self.assertRaises(InvalidToken):
            decrypt_value(encrypted)
        # Restore original key
        set_key(self.test_key)


class TestMaskValue(unittest.TestCase):
    def test_short_value(self):
        assert mask_value("abc") == "****"
        assert mask_value("ab") == "****"

    def test_four_chars(self):
        assert mask_value("abcd") == "****"

    def test_five_chars(self):
        result = mask_value("abcde")
        assert result == "a***e"

    def test_long_value(self):
        result = mask_value("MySecretPassword")
        assert result[0] == "M"
        assert result[-1] == "d"
        assert "*" in result
        assert len(result) == len("MySecretPassword")


# ============================================================
# Validator tests
# ============================================================

class TestValidateParameters(unittest.TestCase):
    def _quote_ledger_params(self):
        return SUPPLIER_QUOTE_LEDGER.parameters

    def test_valid_params(self):
        params = {
            "supplier_portal_url": "https://supplier.example.com",
            "credential_id": "cred_demo",
            "supplier_code": "SUP-001",
            "material_code": "MAT-001",
            "start_date": "2026-01-01",
            "end_date": "2026-03-01",
        }
        result = validate_parameters(self._quote_ledger_params(), params)
        assert result.valid is True
        assert result.errors == []

    def test_missing_required(self):
        params = {"supplier_portal_url": "https://supplier.example.com"}
        result = validate_parameters(self._quote_ledger_params(), params)
        assert result.valid is False
        missing_names = {e.param_name for e in result.errors}
        assert "credential_id" in missing_names

    def test_invalid_url(self):
        params = {
            "supplier_portal_url": "not-a-url",
            "credential_id": "cred_demo",
            "supplier_code": "SUP-001", "material_code": "MAT-001",
            "start_date": "2026-01-01", "end_date": "2026-02-01",
        }
        result = validate_parameters(self._quote_ledger_params(), params)
        assert result.valid is False
        assert any(e.param_name == "supplier_portal_url" for e in result.errors)

    def test_invalid_date(self):
        params = {
            "supplier_portal_url": "https://supplier.example.com",
            "credential_id": "cred_demo",
            "supplier_code": "SUP-001", "material_code": "MAT-001",
            "start_date": "2026-13-01",  # invalid month
            "end_date": "2026-02-01",
        }
        result = validate_parameters(self._quote_ledger_params(), params)
        assert result.valid is False
        assert any(e.param_name == "start_date" for e in result.errors)

    def test_date_range_exceeds_limit(self):
        params = {
            "supplier_portal_url": "https://supplier.example.com",
            "credential_id": "cred_demo",
            "supplier_code": "SUP-001", "material_code": "MAT-001",
            "start_date": "2024-01-01",
            "end_date": "2026-01-01",  # > 365 days
        }
        result = validate_parameters(self._quote_ledger_params(), params)
        assert result.valid is False
        assert any("365 days" in e.message for e in result.errors)

    def test_end_before_start(self):
        params = {
            "supplier_portal_url": "https://supplier.example.com",
            "credential_id": "cred_demo",
            "supplier_code": "SUP-001", "material_code": "MAT-001",
            "start_date": "2026-03-01",
            "end_date": "2026-01-01",
        }
        result = validate_parameters(self._quote_ledger_params(), params)
        assert result.valid is False
        assert any("after start" in e.message for e in result.errors)

    def test_invalid_integer(self):
        params = {
            "purchase_portal_url": "https://procurement.example.com",
            "credential_id": "cred_demo",
            "days_ahead": "not_a_number",
        }
        result = validate_parameters(PURCHASE_ORDER_DUE.parameters, params)
        assert result.valid is False
        assert any(e.param_name == "days_ahead" for e in result.errors)

    def test_optional_with_default_not_required(self):
        """Optional params with defaults should not trigger missing error."""
        params = {
            "purchase_portal_url": "https://procurement.example.com",
            "credential_id": "cred_demo",
            # days_ahead has default="7", department is optional
        }
        result = validate_parameters(PURCHASE_ORDER_DUE.parameters, params)
        assert result.valid is True

    def test_unknown_parameter_is_rejected(self):
        result = validate_parameters(
            PURCHASE_ORDER_DUE.parameters,
            {
                "purchase_portal_url": "https://procurement.example.com",
                "credential_id": "cred_demo",
                "untrusted_url": "https://evil.example.com",
            },
        )
        assert result.valid is False
        assert any(error.param_name == "untrusted_url" for error in result.errors)


# ============================================================
# API Route tests
# ============================================================

class TestWorkflowAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_key = Fernet.generate_key()
        set_key(cls.test_key)

    @classmethod
    def tearDownClass(cls):
        reset_key()

    def setUp(self):
        from enterprise.auth.dependencies import get_current_user
        from enterprise.auth.schemas import DepartmentRole, UserContext
        from enterprise.workflows import routes

        self.app = FastAPI()
        self.app.include_router(routes.router)

        self.user = UserContext(
            user_id="eu_1",
            org_id="org_1",
            department_roles=[
                DepartmentRole(department_id="dept_a", department_name="A", role="operator"),
            ],
            business_line_ids=[],
            procurement_category_ids=["cat_a"],
        )
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.run_task = AsyncMock()
        self.patches = [patch.object(routes.procurement_routes.task_v1_service, "run_task", self.run_task)]
        for active_patch in self.patches:
            active_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    @staticmethod
    def _body(parameters):
        return {"department_id": "dept_a", "category_id": "cat_a", "parameters": parameters}

    def test_list_all_templates(self):
        resp = self.client.get("/enterprise/workflows/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6

    def test_list_by_industry(self):
        resp = self.client.get("/enterprise/workflows/templates?industry=direct_materials")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(t["industry"] == "direct_materials" for t in data)

    def test_list_unknown_industry(self):
        resp = self.client.get("/enterprise/workflows/templates?industry=unknown")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_template_detail(self):
        resp = self.client.get("/enterprise/workflows/templates/tpl_supplier_quote_ledger")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "供应商历史报价台账采集"
        assert len(data["parameters"]) > 0
        assert data["industry"] == "direct_materials"

    def test_get_template_not_found(self):
        resp = self.client.get("/enterprise/workflows/templates/tpl_fake")
        assert resp.status_code == 404

    def test_all_legacy_templates_fail_closed_before_native_task_creation(self):
        for template_id in TEMPLATE_REGISTRY:
            with self.subTest(template_id=template_id):
                response = self.client.post(
                    "/enterprise/workflows/instantiate/" + template_id,
                    json=self._body({}), headers={"Idempotency-Key": "demo"},
                )
                assert response.status_code == 422
                assert "credential reference" in response.json()["detail"]
        self.run_task.assert_not_awaited()

    def test_instantiate_not_found(self):
        response = self.client.post("/enterprise/workflows/instantiate/tpl_fake", json=self._body({}), headers={"Idempotency-Key": "demo"})
        assert response.status_code == 404
        self.run_task.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
