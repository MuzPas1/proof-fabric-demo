"""Document & developer-asset classification (information governance).

Three-tier model — "public by exception":
  * PUBLIC      — served to anyone (product/value/verification/limited examples)
  * ENTERPRISE  — served only to Enterprise Evaluation / staff roles
  * INTERNAL    — never served externally (runbooks, readiness, infra, reports)

Server-side enforcement is the source of truth. Navigation hiding is cosmetic;
this map is what actually gates access in routes/resources_routes.py.
"""
from __future__ import annotations

PUBLIC = "public"
ENTERPRISE = "enterprise"
INTERNAL = "internal"

# Explicit PUBLIC docs — outcome / value / verification / limited examples only.
PUBLIC_DOCS = {
    "README.md",
    "RELEASE_NOTES.md",
    "USE_CASE_CHANGE_RELEASE.md",
    "QUICKSTART.md",  # limited, copy-paste verify/generate examples
}

# Explicit INTERNAL docs — operations / readiness / deployment / internal reports.
INTERNAL_DOCS = {
    "OPERATIONS_RUNBOOK.md",
    "DISASTER_RECOVERY.md",
    "PILOT_DEPLOYMENT_GUIDE.md",
    "PRODUCT_READINESS_ASSESSMENT.md",
    "PRODUCT_READINESS_ASSESSMENT_V2.md",
    "LOAD_TEST_REPORT.md",
}

# Everything else in docs/ (architecture, security, crypto, API ref, integration,
# OpenAPI/Postman/swagger.html, master index, verification audit, KMS/key guides)
# defaults to ENTERPRISE — the "method" tier.
_DEFAULT_DOC = ENTERPRISE


def classify_doc(filename: str) -> str:
    """Return the audience tier for a docs/ file (by basename)."""
    name = filename.rsplit("/", 1)[-1]
    if name in PUBLIC_DOCS:
        return PUBLIC
    if name in INTERNAL_DOCS:
        return INTERNAL
    return _DEFAULT_DOC


def classify_sdk(rel_path: str) -> str:
    """SDK source = proprietary 'method'. All SDK assets are ENTERPRISE.

    (Public verification is demonstrated via limited inline examples in PUBLIC
    docs / the public site, not by exposing the full SDK source anonymously.)
    """
    return ENTERPRISE


# Roles that may access ENTERPRISE assets (staff + approved evaluators).
ENTERPRISE_ROLES = {
    "super_admin", "tenant_admin", "auditor", "external_reviewer", "evaluator",
}
