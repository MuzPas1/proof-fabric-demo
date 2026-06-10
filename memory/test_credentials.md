# PFP — Test Credentials

## Admin (control plane — JWT)
- Email: `admin@pfprotocol.com`
- Password: `PfpAdmin!2026`
- Role: `super_admin`, tenant: `default`
- Login: `POST /api/auth/login` → returns `access_token` (Bearer) + cookies
- Use `Authorization: Bearer <access_token>` for `/api/admin/*` and `/api/auth/me`.

## Sandbox API key (data plane — dev only)
- `X-API-Key: pfp_sandbox_a5fb2bad1924d788c128edf6a31bf1aaa107a9a4`
- Also retrievable from `GET /api/config` (`test_api_key`) in development only.
- Tenant: `default`; scopes: `fea:write, fea:read, fea:verify, webhooks:manage`.
- Used for `/api/fea/*` and `/api/webhooks/*`.

## Notes
- Production (`ENVIRONMENT=production`) does NOT expose the sandbox key via `/api/config`.
- Create additional API keys via `POST /api/admin/api-keys/create` (admin JWT).
- Base URL: from `frontend/.env` → `REACT_APP_BACKEND_URL`.
