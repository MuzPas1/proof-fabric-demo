"""Information Disclosure Reduction Program — backend e2e tests.

Covers:
  1. Doc gating (anonymous) — PUBLIC 200, ENTERPRISE 403 w/ JSON gate, INTERNAL 404.
  2. SDK gating — all ENTERPRISE 403 anon.
  3. OpenAPI gating — full=403 anon, public-curated=200 (no /api/fea/generate, no /admin/).
  4. Evaluation workflow — public submit -> admin list -> admin approve -> creds returned.
  5. Evaluator JWT — gets ENTERPRISE docs/SDK/full OpenAPI; internal still 404; admin endpoints 403.
  6. Backward compat — /api/fea/generate (sandbox key) + /api/public/verify still work; /api/developer ok.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
SANDBOX_KEY = "pfp_sandbox_a5fb2bad1924d788c128edf6a31bf1aaa107a9a4"
ADMIN_EMAIL = "admin@pfprotocol.com"
ADMIN_PASSWORD = "PfpAdmin!2026"


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


# ----------------- 1. Doc gating (anonymous) -----------------
class TestDocGatingAnonymous:
    def test_public_quickstart_200(self, session):
        r = session.get(f"{BASE_URL}/api/resources/docs/QUICKSTART.md")
        assert r.status_code == 200
        assert len(r.text) > 0

    @pytest.mark.parametrize("doc", ["ARCHITECTURE.md", "THREAT_MODEL.md"])
    def test_enterprise_doc_anon_403(self, session, doc):
        r = session.get(f"{BASE_URL}/api/resources/docs/{doc}")
        assert r.status_code == 403, f"{doc}: expected 403 got {r.status_code}"
        body = r.json()
        assert body.get("error") == "enterprise_access_required"
        assert body.get("request_access") == "/evaluation"

    @pytest.mark.parametrize("doc", [
        "OPERATIONS_RUNBOOK.md",
        "PRODUCT_READINESS_ASSESSMENT_V2.md",
        "LOAD_TEST_REPORT.md",
        "DISASTER_RECOVERY.md",
    ])
    def test_internal_doc_anon_404(self, session, doc):
        r = session.get(f"{BASE_URL}/api/resources/docs/{doc}")
        assert r.status_code == 404, f"{doc}: expected 404 got {r.status_code}"

    def test_sdk_anon_403(self, session):
        r = session.get(f"{BASE_URL}/api/resources/sdks/python/pfp_sdk/verify.py")
        assert r.status_code == 403
        assert r.json().get("error") == "enterprise_access_required"


# ----------------- 2. OpenAPI gating (anonymous) -----------------
class TestOpenAPIGating:
    def test_full_spec_anon_403(self, session):
        r = session.get(f"{BASE_URL}/api/openapi.json")
        assert r.status_code == 403
        body = r.json()
        assert body.get("error") == "enterprise_access_required"
        assert body.get("request_access") == "/evaluation"

    def test_public_spec_200_and_curated(self, session):
        r = session.get(f"{BASE_URL}/api/openapi-public.json")
        assert r.status_code == 200
        spec = r.json()
        paths = set(spec.get("paths", {}).keys())
        # Must NOT contain issuance or any admin path
        assert "/api/fea/generate" not in paths, f"fea/generate must NOT be in public spec, got {paths}"
        for p in paths:
            assert "/admin/" not in p, f"admin path leaked into public spec: {p}"
        # Should include public surfaces
        assert any(p.startswith("/api/public/") or p.startswith("/api/demo/")
                   or p in {"/api/health", "/api/config", "/api/developer", "/api/evaluation/request"}
                   for p in paths), f"expected public paths missing: {paths}"

    def test_swagger_ui_200(self, session):
        r = session.get(f"{BASE_URL}/api/docs")
        assert r.status_code == 200
        assert "swagger" in r.text.lower() or "openapi" in r.text.lower()

    def test_redoc_200(self, session):
        r = session.get(f"{BASE_URL}/api/redoc")
        assert r.status_code == 200
        assert "redoc" in r.text.lower()


# ----------------- 3. Evaluation workflow -----------------
@pytest.fixture(scope="session")
def evaluation_artifact(session, admin_token):
    """Create eval request anonymously, then admin lists + approves it.
    Returns dict with request_id, evaluator_email, temporary_password."""
    unique = uuid.uuid4().hex[:10]
    body = {
        "name": "QA Tester",
        "company": "QA Co",
        "business_email": f"qa-eval+{unique}@example.com",
        "industry": "Testing",
        "use_case": "Automated review of doc gating and evaluator access.",
    }
    r = session.post(f"{BASE_URL}/api/evaluation/request", json=body)
    assert r.status_code == 200, f"public submit failed: {r.status_code} {r.text}"
    rj = r.json()
    assert rj.get("status") == "received"
    request_id = rj["request_id"]

    # admin lists pending
    h = {"Authorization": f"Bearer {admin_token}"}
    r2 = session.get(f"{BASE_URL}/api/admin/evaluation/requests?status_filter=pending", headers=h)
    assert r2.status_code == 200
    rids = [it["request_id"] for it in r2.json().get("requests", [])]
    assert request_id in rids, f"new request {request_id} not in pending list"

    # admin approves
    r3 = session.post(f"{BASE_URL}/api/admin/evaluation/requests/{request_id}/approve",
                      headers=h, json={"days": 14})
    assert r3.status_code == 200, f"approve failed: {r3.status_code} {r3.text}"
    aj = r3.json()
    assert "evaluator_email" in aj and "temporary_password" in aj and "expires_at" in aj
    return {
        "request_id": request_id,
        "evaluator_email": aj["evaluator_email"],
        "temporary_password": aj["temporary_password"],
        "expires_at": aj["expires_at"],
    }


class TestEvaluationWorkflow:
    def test_public_submit_no_auth(self, evaluation_artifact):
        # Validated by fixture; assert artifact present
        assert evaluation_artifact["request_id"]
        assert evaluation_artifact["evaluator_email"]
        assert evaluation_artifact["temporary_password"]

    def test_admin_endpoint_requires_auth(self):
        # Use a fresh client (no cookies/headers from admin session)
        r = requests.get(f"{BASE_URL}/api/admin/evaluation/requests")
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code} {r.text[:200]}"


# ----------------- 4. Evaluator access -----------------
@pytest.fixture(scope="session")
def evaluator_token(session, evaluation_artifact):
    r = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": evaluation_artifact["evaluator_email"],
        "password": evaluation_artifact["temporary_password"],
    })
    assert r.status_code == 200, f"evaluator login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


class TestEvaluatorAccess:
    def test_enterprise_doc_with_evaluator_200(self, session, evaluator_token):
        h = {"Authorization": f"Bearer {evaluator_token}"}
        r = session.get(f"{BASE_URL}/api/resources/docs/ARCHITECTURE.md", headers=h)
        assert r.status_code == 200, r.text[:200]

    def test_sdk_with_evaluator_200(self, session, evaluator_token):
        h = {"Authorization": f"Bearer {evaluator_token}"}
        r = session.get(f"{BASE_URL}/api/resources/sdks/python/pfp_sdk/verify.py", headers=h)
        assert r.status_code == 200

    def test_full_openapi_with_evaluator_200(self, session, evaluator_token):
        h = {"Authorization": f"Bearer {evaluator_token}"}
        r = session.get(f"{BASE_URL}/api/openapi.json", headers=h)
        assert r.status_code == 200
        # Full spec should include issuance and admin paths
        paths = set(r.json().get("paths", {}).keys())
        assert "/api/fea/generate" in paths
        assert any("/admin/" in p for p in paths)

    def test_internal_doc_still_404_for_evaluator(self, session, evaluator_token):
        h = {"Authorization": f"Bearer {evaluator_token}"}
        r = session.get(f"{BASE_URL}/api/resources/docs/OPERATIONS_RUNBOOK.md", headers=h)
        assert r.status_code == 404

    def test_evaluator_blocked_from_admin(self, session, evaluator_token):
        h = {"Authorization": f"Bearer {evaluator_token}"}
        r = session.get(f"{BASE_URL}/api/admin/evaluation/requests", headers=h)
        assert r.status_code == 403


# ----------------- 5. Backward compatibility -----------------
class TestBackwardCompat:
    def test_fea_generate_and_public_verify(self, session):
        h = {"X-API-Key": SANDBOX_KEY}
        unique = uuid.uuid4().hex[:10]
        payload = {
            "idempotency_key": f"TEST_IK_{int(time.time()*1000)}_{unique}",
            "transaction_id": f"TEST_TXN_{int(time.time()*1000)}_{unique}",
            "timestamp": "2026-01-15T12:00:00Z",
            "amount": 4200,
            "currency": "USD",
            "payer_id": "TEST_payer",
            "payee_id": "TEST_payee",
        }
        r = session.post(f"{BASE_URL}/api/fea/generate", headers=h, json=payload)
        assert r.status_code in (200, 201), f"fea/generate failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        fea_id = body.get("fea_id") or body.get("proof", {}).get("fea_id") or body.get("id")
        assert fea_id, f"no fea_id in response: {body}"

        # public verify
        rv = session.get(f"{BASE_URL}/api/public/verify/{fea_id}")
        assert rv.status_code == 200
        assert rv.json().get("signature_valid") is True

    def test_developer_block(self, session):
        r = session.get(f"{BASE_URL}/api/developer")
        assert r.status_code == 200
        body = r.json()
        # access_model with public/enterprise blocks + signing
        assert "access_model" in body or "public" in body, f"missing access_model: {list(body.keys())}"
        assert "signing" in body

    def test_admin_dashboard_still_works(self, session, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = session.get(f"{BASE_URL}/api/auth/me", headers=h)
        assert r.status_code == 200
        assert r.json().get("email") == ADMIN_EMAIL


# ----------------- Cleanup -----------------
@pytest.fixture(scope="session", autouse=True)
def _final_cleanup(session, request):
    yield
    # Best-effort: nothing to clean — evaluator accounts auto-expire.
