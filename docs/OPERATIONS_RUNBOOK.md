# PFP — Operations Runbook

## 1. Service management
- Process manager: supervisor (`backend`, `frontend`). Restart backend:
  `sudo supervisorctl restart backend`.
- Logs: structured JSON to stdout (captured by supervisor / cluster log driver).
- Health: `GET /api/health` returns `status: healthy|degraded` with per-component
  checks (`database`, `key_registry`, `signing_service`, `demo_db`). Wire this to
  your load balancer readiness probe.
- Metrics: `GET /api/metrics` (Prometheus). Scrape interval 15s recommended.

## 2. Key dashboards / alerts
| Signal | Source | Alert |
|---|---|---|
| Request error rate | `pfp_http_requests_total{status=~"5.."}` | >1% 5m |
| Latency p99 | `pfp_http_request_duration_seconds` | >500ms 5m |
| FEA issuance rate | `pfp_fea_generated_total` | anomaly |
| Verify failures | `pfp_fea_verified_total{result="invalid"}` | spike |
| Health degraded | `/api/health` checks false | page on-call |

## 3. Common operations
### Provision a customer API key
```
POST /api/admin/api-keys/create  (admin JWT)
{ "name": "acme-prod", "customer_id": "acme", "scopes": ["fea:write","fea:read","fea:verify"], "expires_in_days": 90 }
```
Return the `api_key` to the customer over a secure channel — it is shown once.

### Revoke an API key
```
POST /api/admin/api-keys/revoke?key_id=<uuid>
```

### Create a tenant (super_admin)
```
POST /api/admin/tenants { "name": "Acme Bank" }
```

### Inspect / verify audit log
```
GET /api/admin/audit?limit=100
GET /api/admin/audit/verify    # must return {"intact": true, ...}
```

## 4. Incident: suspected key compromise
1. **Revoke** the affected signing key: `POST /api/admin/keys/revoke?public_key_id=<kid>`
   (takes effect immediately at verify time).
2. **Rotate**: `POST /api/admin/keys/rotate` → capture `new_private_seed_b64`.
3. Store the new seed in the KMS/secret store; update `PRIVATE_KEY` ref.
4. Restart the service so issuance uses the new key.
5. Communicate the revoked `kid` to verifiers; re-issue affected FEAs if needed.
6. Confirm audit chain integrity (`/api/admin/audit/verify`).

## 5. Incident: API abuse / DoS
1. Identify offending source from metrics/logs.
2. Block at ingress/WAF; tighten rate limits if needed.
3. For demo abuse: data is isolated in the demo DB — purge `demo_proofs` safely
   without touching production.

## 6. Backups
- MongoDB: daily full + oplog for PITR. Verify restores monthly.
- Critical collections: `feas`, `key_registry`, `api_keys`, `users`, `tenants`,
  `audit_log`. See `DISASTER_RECOVERY.md`.

## 7. Configuration reference (env)
`ENVIRONMENT`, `MONGO_URL`, `DB_NAME`, `DEMO_DB_NAME`, `JWT_SECRET`,
`ADMIN_EMAIL`, `ADMIN_PASSWORD`, `KMS_PROVIDER`, `PRIVATE_KEY`/`DEMO_PRIVATE_KEY`
(local) or `*_KEY_REF_*` (cloud), `CORS_ORIGINS`, `MAX_REQUEST_BYTES`,
`ACCEPT_LEGACY_V1`, `ENFORCE_VERIFY_TIMESTAMP`, `SANDBOX_API_KEY` (dev only),
`DEFAULT_TENANT_ID`.

## 8. Production checklist
- [ ] `ENVIRONMENT=production` (disables sandbox key exposure)
- [ ] `KMS_PROVIDER` ≠ `local`; signing keys in cloud KMS/secret store
- [ ] `CORS_ORIGINS` set to explicit partner origins
- [ ] MongoDB with TLS + auth (`mongodb+srv`, credentials)
- [ ] `JWT_SECRET` rotated from any default; strong `ADMIN_PASSWORD`
- [ ] Backups + restore test green
- [ ] Prometheus scrape + alerts wired
