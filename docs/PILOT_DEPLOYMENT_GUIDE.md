# PFP — Pilot Deployment Guide

A checklist-driven path to a supervised, single-tenant (or multi-tenant) pilot.

## 1. Prerequisites
- Kubernetes cluster (EKS/GKE/AKS) or Docker host.
- Managed MongoDB with **TLS + auth** (Atlas, DocumentDB, CosmosDB Mongo API).
- Cloud secret store / KMS (AWS Secrets Manager, GCP Secret Manager, Azure Key
  Vault) for the signing seeds.
- TLS certificate (cert-manager / managed cert).

## 2. Generate signing keys (once)
```bash
python - <<'PY'
import base64, os
print("PRODUCTION_SEED=", base64.b64encode(os.urandom(32)).decode())
print("DEMO_SEED=",       base64.b64encode(os.urandom(32)).decode())
PY
```
Store both in your secret store. Reference them via `AWS_KEY_REF_PRODUCTION` /
`AWS_KEY_REF_DEMO` (or the GCP/Azure equivalents) and set `KMS_PROVIDER`
accordingly. **Never** ship `KMS_PROVIDER=local` to production.

## 3. Configure secrets (Terraform)
```bash
cd deploy/terraform
terraform init
terraform apply \
  -var cloud=aws \
  -var mongo_url='mongodb+srv://USER:PASS@cluster/?tls=true&authSource=admin' \
  -var jwt_secret="$(python -c 'import secrets;print(secrets.token_hex(32))')" \
  -var admin_email=admin@pfprotocol.com \
  -var admin_password='STRONG_PASSWORD' \
  -var production_seed="$PRODUCTION_SEED" \
  -var demo_seed="$DEMO_SEED" \
  -var cors_origins='https://app.partner.com'
```

## 4. Deploy (Helm)
```bash
docker build -f deploy/Dockerfile -t ghcr.io/pfprotocol/pfp-backend:2.0.0 .
docker push ghcr.io/pfprotocol/pfp-backend:2.0.0
helm upgrade --install pfp deploy/helm/pfp -n pfp --create-namespace
```

## 5. Smoke test
```bash
BASE=https://api.partner.com
curl -s $BASE/api/health            # expect {"status":"healthy", checks:{...:true}}
curl -s $BASE/api/config            # expect NO test_api_key in production
# Admin login + provision a key:
TOK=$(curl -s -X POST $BASE/api/auth/login -d '{"email":"admin@pfprotocol.com","password":"STRONG_PASSWORD"}' -H 'Content-Type: application/json' | jq -r .access_token)
curl -s -X POST $BASE/api/admin/api-keys/create -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"name":"pilot","expires_in_days":90}'
```

## 6. Provision the partner
1. Create a tenant: `POST /api/admin/tenants {"name":"Partner Bank"}`.
2. Create a tenant-scoped API key for that tenant.
3. Share the key + base URL + `tenant_id` with the partner securely.
4. Point them at `docs/INTEGRATION_GUIDE.md` and the SDK for their stack.

## 7. Observability
- Prometheus scrape `/api/metrics` (annotations already set on the pods).
- Alerts per `OPERATIONS_RUNBOOK.md` §2.
- Centralized JSON logs.

## 8. Go/No-Go checklist
- [ ] `ENVIRONMENT=production`, sandbox key NOT exposed
- [ ] `KMS_PROVIDER` cloud-backed; no plaintext seed on disk
- [ ] MongoDB TLS + auth verified
- [ ] CORS limited to partner origins
- [ ] `/api/health` all-green; metrics flowing
- [ ] Backup + restore drill passed (`DISASTER_RECOVERY.md`)
- [ ] Key rotation rehearsed (`KEY_ROTATION_GUIDE.md`)
- [ ] Audit chain verifies (`GET /api/admin/audit/verify`)
- [ ] Partner verified an FEA **independently** via an SDK
