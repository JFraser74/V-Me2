# Operations & Admin Notes

...existing operations docs...

## Ops Orchestrator (MVP)

**What it does:** Create small build/deploy tasks, stream progress via SSE, and (optionally) persist to Supabase.
- Works **without Supabase** (in-proc fallback).  
- When `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` are set, tasks/events are stored in **va_tasks** and **va_task_events**.

### Endpoints (admin-gated)
Header: `X-Admin-Token: $SETTINGS_ADMIN_TOKEN`  
(EventSource can’t set headers; for dev only you may use `?admin_token=$TOKEN` query param.)

- `POST /ops/tasks` → create a task  
  Body: `{ "title": "Build X", "body": "optional notes" }`  
  Returns: `{ "id": "<task_id>", "status": "queued" }`

- `GET /ops/tasks` → list recent tasks

- `GET /ops/tasks/{id}` → task detail

- `POST /ops/tasks/{id}/cancel` → best-effort cancel

- `GET /ops/tasks/{id}/stream` → **SSE** (server-sent events)  
  - **Dev mode:** set `DEV_LOCAL_LLM=1` → deterministic 4 ticks then `done`.

### Quick start (dev)
```bash
export SETTINGS_ADMIN_TOKEN=adm DEV_LOCAL_LLM=1
curl -s -H "X-Admin-Token: $SETTINGS_ADMIN_TOKEN" \
  -H "content-type: application/json" \
  -d '{"title":"Example task"}' \
  http://localhost:8080/ops/tasks

# stream logs (dev can use admin_token on query)
curl -N "http://localhost:8080/ops/tasks/1/stream?admin_token=$SETTINGS_ADMIN_TOKEN"
```

Notes

SSE auth: browsers can’t add custom headers to EventSource, so dev uses ?admin_token=….  
Planned: ephemeral signed stream_token returned by POST /ops/tasks, validated by /stream.

Persisted schema: va_tasks(id, created_at, title, status); va_task_events(id, created_at, task_id, kind, data_json).
