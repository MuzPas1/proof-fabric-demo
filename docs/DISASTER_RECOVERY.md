# PFP — Disaster Recovery Guide

## Objectives
- **RPO** (max data loss): ≤ 5 minutes (oplog/PITR).
- **RTO** (max downtime): ≤ 60 minutes.

## 1. What must be protected
| Asset | Store | Recovery source |
|---|---|---|
| Issued FEAs | `feas` | MongoDB backup |
| Public key registry | `key_registry` | MongoDB backup (immutable history) |
| API keys | `api_keys` | MongoDB backup |
| Users / tenants | `users`, `tenants` | MongoDB backup |
| Audit trail | `audit_log` | MongoDB backup (verify chain after restore) |
| **Signing private keys** | **KMS / secret store** | KMS backup / re-import |

> The signing private key is **not** in MongoDB. Losing it means no new FEAs can
> be signed under the current `kid` (existing FEAs remain verifiable via the
> public key registry). Protect KMS material with its own backup/replication.

## 2. Backup strategy
- MongoDB: nightly `mongodump` (or managed snapshots) + continuous oplog for
  point-in-time recovery. Encrypt backups at rest; store off-region.
- KMS: rely on the cloud KMS's durability + cross-region replication; export an
  encrypted escrow copy of seeds to a sealed secret store if policy allows.
- Configuration: env/secret manifests stored in version control (without
  secrets) + secret manager.

## 3. Recovery procedures

### 3.1 Restore MongoDB
1. Provision a clean MongoDB (TLS + auth).
2. `mongorestore` latest snapshot; apply oplog to target timestamp (PITR).
3. Point `MONGO_URL` / `DB_NAME` / `DEMO_DB_NAME` at the restored cluster.
4. Restart backend; confirm `GET /api/health` → `healthy`.
5. **Verify audit chain**: `GET /api/admin/audit/verify` must return
   `{"intact": true}`. If broken, investigate before resuming writes.

### 3.2 Restore signing capability
1. Ensure the KMS provider has the production key (or re-import the escrowed
   seed). Set `KMS_PROVIDER` + key refs.
2. Restart; `signing_service` health check must pass.
3. If the key is unrecoverable: rotate to a new key
   (`POST /api/admin/keys/rotate`), publish the new `kid`, and re-issue
   in-flight FEAs as required. Old FEAs still verify against the retired key in
   the registry.

### 3.3 Full region failover
1. Stand up the app in the secondary region (Helm/Terraform — see
   `PILOT_DEPLOYMENT_GUIDE.md`).
2. Connect to the cross-region MongoDB replica (promote if needed).
3. Connect to the replicated KMS key.
4. Switch DNS/ingress to the secondary region.

## 4. Post-recovery validation
- [ ] `GET /api/health` healthy (all 4 checks true)
- [ ] Generate a test FEA and verify it locally with an SDK
- [ ] `GET /api/admin/audit/verify` intact
- [ ] Public key registry contains expected active/retired keys
- [ ] Metrics flowing to Prometheus

## 5. DR testing cadence
- Monthly: backup restore drill (non-prod).
- Quarterly: full region failover game-day.
