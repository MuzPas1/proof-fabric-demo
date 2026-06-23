# PFP Information-Disclosure & Commercialization Strategy (READ-ONLY review)
Date: 2026-06-18 · Status: ASSESSMENT (no code changed) · Owner: enterprise architect

## Current public footprint (empirically verified)
Public (no auth): `/`, `/demo`, `/developers`, `/docs/*`, `/verify`;
`/api/docs` (Swagger), `/api/redoc`, `/api/openapi.json`;
`/api/resources/docs/*` (ENTIRE docs/ dir as open static files);
`/api/resources/sdks/*` (ENTIRE SDK source tree); `/api/developer` manifest.

## Confirmed over-exposure (HTTP 200 to anonymous)
- Static docs mount serves files NOT in the portal nav too: OPERATIONS_RUNBOOK,
  THREAT_MODEL, DISASTER_RECOVERY, PRODUCT_READINESS_ASSESSMENT(_V2),
  LOAD_TEST_REPORT, PFP_VERIFICATION_AUDIT, KEY_ROTATION_GUIDE, KMS_MIGRATION,
  PILOT_DEPLOYMENT_GUIDE — all reachable by URL.
- Public `/docs` nav itself lists THREAT_MODEL, OPERATIONS_RUNBOOK,
  DISASTER_RECOVERY, KEY_ROTATION, PILOT_DEPLOYMENT, PRODUCT_READINESS_V2.
- SDK source (canonicalize/verify impl, test vectors, generators) fully public.
- Swagger/Redoc/OpenAPI expose ALL admin + federated + BYOS + signer endpoints.

## GitHub exposure (git-tracked working tree)
- CRITICAL: memory/test_credentials.md (plaintext admin+reviewer passwords, API keys) IS tracked.
- Internal strategy tracked: memory/PRD.md, memory/CRYPTO_AGILITY_IMPLEMENTATION_PLAN.md,
  test_result.md, test_reports/iteration_*.json.
- Infra-as-code tracked: deploy/terraform/main.tf, deploy/k8s/*, deploy/helm/*, deploy/Dockerfile.
- backend/.env NOT currently tracked, but .gitignore intentionally does not ignore .env (fragile).

## Classification decision (target model)
PUBLIC: product/value/use-cases, demo portal, /verify, high-level trust page,
trimmed Quickstart + a few curl examples, RELEASE_NOTES (high-level), contact/CTAs.
ENTERPRISE (gated eval center): API_REFERENCE, DEVELOPER_GUIDE, INTEGRATION_GUIDE,
OpenAPI/Swagger/Redoc/Postman, SDK docs+source, ARCHITECTURE, CRYPTOGRAPHIC_ARCHITECTURE,
CRYPTO_AGILITY, CANONICALIZATION_SPEC, SECURITY_ARCHITECTURE, KMS_MIGRATION_GUIDE (sanitized),
THREAT_MODEL (sanitized), PFP_VERIFICATION_AUDIT, CANONICAL_ENDPOINTS, PFP_MASTER_INDEX,
KEY_ROTATION_GUIDE (sanitized).
INTERNAL ONLY (remove from public + private repo): OPERATIONS_RUNBOOK, DISASTER_RECOVERY,
PILOT_DEPLOYMENT_GUIDE, PRODUCT_READINESS_ASSESSMENT(_V2), LOAD_TEST_REPORT, deploy/*,
memory/*, test_reports/*, test_result.md.

## Recommended remediation (priority order) — NOT yet executed, awaiting approval
P0 Secrets/IP: untrack memory/test_credentials.md (+ memory/, test_reports/, test_result.md),
   rotate the leaked admin/reviewer passwords + API keys, explicitly gitignore .env, move
   deploy/* + internal docs to a private repo.
P0 Gating: replace open StaticFiles mounts with an auth-gated docs/SDK endpoint; serve only
   PUBLIC-class docs anonymously; gate Swagger/Redoc/OpenAPI (or publish a curated public-API-only spec).
P1 Public site refocus: rewrite landing/docs to product/value/use-case; add Enterprise Evaluation
   Center (lead-capture form -> evaluator role/JWT, time-boxed) unlocking technical materials.
P1 OpenAPI split: public spec = verify/demo/limited-generate only; full spec behind eval auth.
P2 Lead gen: Request Demo / Request Evaluation / Contact Sales / Partnership CTAs + analytics.

## Future governance model
Three-tier disclosure (Public / Enterprise-NDA / Internal), private infra repo,
"public by exception" doc policy, watermarked/time-boxed eval access, secret-scanning in CI.
