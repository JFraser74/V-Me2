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


### Voice MVP (Whisper)

This project includes a small Voice MVP that accepts audio uploads and forwards
them to the OpenAI Whisper transcription API. There are two modes:

- Fake mode: set `VOICE_FAKE=1` to avoid calling external services (used in CI/local tests).
- Real mode: set `VOICE_FAKE=0` and provide `OPENAI_API_KEY` in the environment.

Notes:
- File size cap: 15 MB. Supported uploads: `audio/webm` (MediaRecorder), `wav`, `m4a`.
- The endpoint is `/api/audio/upload`. In fake mode the response includes `"fake": true`.
- For production, run behind HTTPS and set `VOICE_FAKE=0` and `OPENAI_API_KEY`.


### Meeting Mode (real)

This repository ships a Meeting Mode with a fake in-memory store for tests. To run in real mode against Supabase:

- Apply the `db/schema.sql` file in the Supabase SQL editor (or run via psql against your `DATABASE_URL`).
- Set environment variables:
  - `MEETING_FAKE=0`
  - `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (service role) in your environment.
- Start the server and exercise the endpoints:
  1. POST `/api/meeting/begin` — creates a meeting row and returns a numeric `meeting_id` when successful.
  2. POST `/api/meeting/ingest` — send segments with that numeric `meeting_id`.
  3. POST `/api/meeting/end` — returns the summary; the server will attempt to update the `va_meetings` row with the summary and bullets.

Manual validation: use the Supabase Table Editor to confirm rows are present in `va_meetings` and `va_meeting_segments`.

Notes: this PR implements write-only, best-effort behavior — failures to persist do not change endpoint responses. The Service Role key bypasses RLS; configure policies as desired.


### Threads API (Coding panel)

The Coding panel uses a small Threads API to persist and restore chat-like threads. Endpoints:

- POST `/api/threads` — create a session (body: optional `label`). Returns `{id, title}`.
- PUT `/api/threads/{id}/title` — update the session label. Returns `{ok,id,title}`.
- GET `/api/threads?limit=20` — return recent named sessions: `{items:[{id,title,created_at}]}`.
- GET `/api/threads/{id}/messages` — return ordered messages for a session: `{items:[{id,role,content,created_at}]}`.

These endpoints are best-effort: if Supabase isn't configured the API returns empty lists or `{ok:false}` responses and the UI should handle empty results gracefully.

