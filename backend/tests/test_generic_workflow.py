"""
Backend tests for the Generic Workflow Builder support in /api/demo/issue and
/api/demo/verify/{proof_id}.

Verifies:
  - custom_fields (ordered list) + check-only industry payload are accepted,
    embedded in the canonical payload, and returned on verify.
  - Field ORDER is preserved deterministically (reordering changes the proof_id).
  - Checks without a `desc` are accepted (Generic Workflow Builder checks).
  - Existing curated-industry payloads (with desc + context) still work
    (backward compatibility / regression).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://trust-layer-12.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"

HEX64 = lambda s: isinstance(s, str) and len(s) == 64 and all(
    c in "0123456789abcdef" for c in s
)

COMPLIANT = {
    "kyc": "Pass",
    "aml": "Pass",
    "limits": "Within allowed range",
    "status": "COMPLIANT",
}
NON_COMPLIANT = {
    "kyc": "Fail",
    "aml": "Pass",
    "limits": "Within allowed range",
    "status": "NON-COMPLIANT",
}

BASE_TXN = {
    "transaction_id": "Release",
    "user_id": "generic-workflow",
    "amount": "0.00",
    "created_at": "2026-01-15T10:00:00Z",
}


def _builder_industry(fields, checks, status="Pass"):
    return {
        "id": "generic_builder",
        "label": "Release",
        "checks": [{"name": c, "status": status} for c in checks],
        "custom_fields": [{"label": l, "value": v} for (l, v) in fields],
    }


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestGenericWorkflowBuilder:
    def test_issue_with_custom_fields_and_checks(self, api_client):
        industry = _builder_industry(
            [("Release ID", "REL-2026-001"), ("Environment", "Production")],
            ["Test Execution", "UAT Completion", "CAB Approval"],
        )
        r = api_client.post(
            f"{API}/demo/issue",
            json={**BASE_TXN, "compliance": COMPLIANT, "industry": industry},
        )
        assert r.status_code == 200, r.text
        pid = r.json()["proof_id"]
        assert HEX64(pid)

        v = api_client.get(f"{API}/demo/verify/{pid}")
        assert v.status_code == 200
        data = v.json()
        assert data["valid"] is True
        ind = data["industry"]
        assert ind["id"] == "generic_builder"
        assert ind["custom_fields"] == [
            {"label": "Release ID", "value": "REL-2026-001"},
            {"label": "Environment", "value": "Production"},
        ]
        assert [c["name"] for c in ind["checks"]] == [
            "Test Execution",
            "UAT Completion",
            "CAB Approval",
        ]
        # Generic builder checks carry no description.
        assert all("desc" not in c for c in ind["checks"])

    def test_field_order_changes_proof_id(self, api_client):
        a = _builder_industry(
            [("A", "1"), ("B", "2")], ["Check One"]
        )
        b = _builder_industry(
            [("B", "2"), ("A", "1")], ["Check One"]
        )
        ra = api_client.post(
            f"{API}/demo/issue", json={**BASE_TXN, "compliance": COMPLIANT, "industry": a}
        ).json()
        rb = api_client.post(
            f"{API}/demo/issue", json={**BASE_TXN, "compliance": COMPLIANT, "industry": b}
        ).json()
        # Different visible field order => different canonical payload => different proof.
        assert ra["proof_id"] != rb["proof_id"]

    def test_simulate_failure_marks_all_checks_failed(self, api_client):
        industry = _builder_industry(
            [("Ticket ID", "TIC-9")], ["Triage", "Approval"], status="Fail"
        )
        r = api_client.post(
            f"{API}/demo/issue",
            json={**BASE_TXN, "compliance": NON_COMPLIANT, "industry": industry},
        )
        assert r.status_code == 200, r.text
        pid = r.json()["proof_id"]
        v = api_client.get(f"{API}/demo/verify/{pid}").json()
        assert v["valid"] is True
        assert all(c["status"] == "Fail" for c in v["industry"]["checks"])
        assert v["compliance"]["status"] == "NON-COMPLIANT"


class TestCuratedIndustryStillWorks:
    def test_curated_industry_with_desc_and_context(self, api_client):
        industry = {
            "id": "change_release",
            "label": "Release Readiness Evaluation",
            "checks": [
                {
                    "name": "Test Execution Proof",
                    "desc": "Confirms tests executed and passed.",
                    "status": "Pass",
                }
            ],
            "context": {"Release Name": "Payments v4.2", "Environment": "Production"},
        }
        r = api_client.post(
            f"{API}/demo/issue",
            json={**BASE_TXN, "compliance": COMPLIANT, "industry": industry},
        )
        assert r.status_code == 200, r.text
        pid = r.json()["proof_id"]
        v = api_client.get(f"{API}/demo/verify/{pid}").json()
        assert v["valid"] is True
        assert v["industry"]["checks"][0]["desc"] == "Confirms tests executed and passed."
        assert v["industry"]["context"]["Release Name"] == "Payments v4.2"
