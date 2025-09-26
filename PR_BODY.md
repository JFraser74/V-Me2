Summary

Dual-token auth for settings API: server now accepts either a stable CI token (CI_SETTINGS_ADMIN_TOKEN) or the runtime/UI-rotatable token (SETTINGS_ADMIN_TOKEN).

CI updated to use CI_SETTINGS_ADMIN_TOKEN; runtime rotation no longer breaks CI smoke.

Smoke workflow & scripts: smoke.yml, smoke_all.sh (with --save), and railway_preflight.sh.

Railway import stability: package markers + PYTHONPATH=. in Procfile.

Tests + local/deployed smoke verified.

Why

Rotating the admin token via the UI/Supabase previously broke CI. Separating a stable CI token from the runtime/UI token lets operators rotate production safely without touching GitHub secrets.

Changes

main.py: centralized _allowed_admin_tokens(); settings endpoints use it.

.github/workflows/smoke.yml: uses CI_SETTINGS_ADMIN_TOKEN (step env only); uploads smoke_out artifact.

scripts/smoke_all.sh: one-click smoke; auto-start local server; polling tool-events clamp; --save/SMOKE_SAVE_DIR.

scripts/railway_preflight.sh: deployment env sanity checks (+ optional smoke).

Procfile: web: PYTHONPATH=. python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --app-dir .

Added __init__.py package markers; repo imports unified under vme_lib.

Tests: added/updated settings + tool_events clamp tests (all green locally).

Security / Secrets

CI: uses repo/org secret CI_SETTINGS_ADMIN_TOKEN (stable; not rotated by UI).

Runtime: SETTINGS_ADMIN_TOKEN lives in Railway and/or Supabase va_settings and can be rotated from the UI.

Secrets only appear in step-level env (linter-friendly; no forks exposure).

Verification

pytest: 7 passed, 2 warnings.

Local + deployed smoke (Railway):

/health → 200

/api/settings → 200 with new runtime token; 403 with old token

Chat endpoints → 200

Tool-events clamp → validated when session/events present

smoke_out JSON saved locally and uploaded by workflow.

Deploy / Config

GitHub (already done):

Add secret CI_SETTINGS_ADMIN_TOKEN (✅)

Remove secret SETTINGS_ADMIN_TOKEN to avoid confusion (✅)

Railway / Runtime:

Ensure SETTINGS_ADMIN_TOKEN is set (✅)

Optional: store token in Supabase va_settings for UI rotation (✅)

Risk & Rollback

Low risk. Routes gated behind token logic consolidated but behavior is backwards compatible.

Rollback: revert to previous commit; CI still fine since CI token is independent.

Post-merge Runbook

Trigger Actions → “Smoke (deployed)” with base_url=https://<your-app>.railway.app.

(Optional) On Railway shell: scripts/railway_preflight.sh (set RUN_SMOKE=1 to auto-run smoke).

Review smoke_out artifact (pretty JSON traces for quick triage).

Checklist (merge gate)

 CI secret CI_SETTINGS_ADMIN_TOKEN exists in GitHub.

 Runtime SETTINGS_ADMIN_TOKEN set in Railway (and/or Supabase).

 pytest green.

 Manual smoke passes against deployed URL (or acceptable warns for missing optional deps).

 README updated with dual-token policy (✅).

Notes for Agents

CI never depends on the UI token again. Rotate SETTINGS_ADMIN_TOKEN freely via UI; CI keeps working.

Use scripts/smoke_all.sh --save .smoke_out locally; in CI see the smoke_out artifact.
