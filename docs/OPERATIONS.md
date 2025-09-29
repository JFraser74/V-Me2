## V-Me2 Operations and Security Notes

This document describes the runtime requirements for admin tokens, Supabase, and the Bridge peer registry.

1. Admin tokens
  - `SETTINGS_ADMIN_TOKEN` protects the `/api/settings` and `/api/bridge/*` endpoints.
  - `CI_SETTINGS_ADMIN_TOKEN` is an optional token used for CI / automation.
  - Tokens may be provided via environment variables or stored in `va_settings` (encrypted when `APP_ENCRYPTION_KEY` is set).

2. Supabase
  - Provide `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for full server-side operation.
  - Apply schema in `db/schema.sql` via Supabase SQL editor or using psql with `DATABASE_URL`.

3. Encryption
  - `APP_ENCRYPTION_KEY` (Fernet) enables encryption of secret settings stored in Supabase. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

4. Bridge peer registry
  - Peers are writable via `/api/bridge/peers` and require admin tokens.
  - Local file fallback (`.vme2_settings.json`) stores non-secret info only (names + urls). Tokens are never written to disk unless you explicitly add local encryption.
  - Rate limiting: per-admin token in-memory counter to prevent bursts. Configure with `BRIDGE_MAX_CALLS`.

5. Smoke and CI
  - Use `SMOKE` scripts with `SETTINGS_ADMIN_TOKEN` or `CI_SETTINGS_ADMIN_TOKEN` set in the environment.

6. Rotating tokens
  - Use the `/api/settings/rotate_admin` endpoint (protected by admin token) to generate a new `SETTINGS_ADMIN_TOKEN` and persist it. Update environment/CI secrets as needed.

7. Debugging
  - `/api/_debug/supacall` and `/api/_debug/railway_inspect` exist to help diagnose deployment issues (they are intentionally minimal and do not return secret values).

Keep secrets out of git and use your platform secret manager for production deployments.

## Importing legacy VA-min data into V-Me2

Recommended approach: keep VA-min as a read-only legacy source and import selected tables into V-Me2 via a controlled ETL. Do NOT merge the DBs live.

Quick import steps:

1. Set a VA_MIN_DSN in your environment or pass via --source-dsn. Optionally store it encrypted in `va_settings` via `--store-config`.
2. Run the importer in dry-run mode first:

```bash
VA_MIN_DSN="postgres://..." python scripts/import_va_min.py --source-table messages --target-table va_messages --key-columns message_id --limit 1000 --dry-run
```

3. If the dry-run looks good, run without `--dry-run` and with an appropriate --batch-size. Monitor the console output and the `va_settings` mapping if you have one.

4. After import, check the V-Me2 tables and the optional `legacy_map` table to ensure auditability.

Notes:
- The importer is idempotent when key-columns identify the row uniquely. It upserts rows and skips/updates depending on presence.
- For embeddings you may want to re-embed lazily in V-Me2 if models differ.
- If you want tokens or DSNs stored, use the `APP_ENCRYPTION_KEY` so they are encrypted in Supabase.
