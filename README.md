# V-Me2
Virtual Assistant

Quick local bring-up
```
# install deps (adds langgraph)
pip install -r requirements.txt langgraph

# run the app
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```



Quick deployment checklist (Railway / Heroku-style)
-------------------------------------------------

1) Ensure environment variables are set in your host (Railway -> Variables):
	- SUPABASE_URL
	- SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY for read-only)
	- OPENAI_API_KEY (optional — enables LLM replies)

2) Procfile: this repository contains a `Procfile` with the recommended start:

	web: python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}

3) After deploy, verify with Railway Shell (or Logs):

	curl -fsS http://127.0.0.1:${PORT:-8080}/health
	curl -fsS http://127.0.0.1:${PORT:-8080}/showme | head -n 5

4) If the app responds with HTTP 200 on /health and serves /showme, try a smoke POST:

	curl -fsS -X POST http://127.0.0.1:${PORT:-8080}/agent/chat \
	  -H 'content-type: application/json' \
	  -d '{"message":"hello from deploy","label":"deploy-test"}'

	If the response is an echo, the app is running. If you set `OPENAI_API_KEY`, you should get LLM generated text.

UI notes and tooltips
---------------------
- Coding tab: use the `Read` button to fetch file contents (via `/agent/read`). Use Preview Save to dry-run; set `confirm=true` (Save button) to persist via `/agent/write`.
- PDF tab: paste a remote PDF URL and hit Load, or upload a local PDF file to preview it in the iframe.
- Settings: the UI will try to GET `/api/settings` and POST updates to it if present. The UI gracefully degrades when that endpoint is not available.

Open http://127.0.0.1:8000/ui and send a message. If `OPENAI_API_KEY` is not
set the agent will respond with an echo (safe local fallback).

Environment variables you may set:
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
- OPENAI_API_KEY (optional - enables LLM driven agent)
- OPENAI_MODEL (optional, defaults to gpt-4o-mini)

Agent runtime flags
-------------------
- AGENT_USE_LANGGRAPH: when set to '1' or 'true', the application will attempt
	to construct the real LangGraph + OpenAI-backed agent (requires OPENAI_API_KEY).
	This is intentionally off by default in test/dev environments to avoid
	accidental external API calls. In CI you may set the repository secret
	LANGGRAPH_ENABLED and OPENAI_API_KEY to enable full-agent tests.

- DEV_LOCAL_LLM: when set to '1' or 'true', the `/agent/chat` endpoint returns
	a deterministic local echo (no external LLM calls). Useful for development
	and debugging when you don't want to use OpenAI.

Developer tool examples (via tools/codespace.py and tools/supabase_tools.py):

Python examples:
```py
from tools import codespace, supabase_tools as sbt
print(codespace.ls('.'))
print(codespace.read_file('main.py'))
print(sbt.sb_select('va_sessions', limit=3))
```

HTTP examples (smoke tests):
```
curl -s localhost:8000/health
curl -s -X POST localhost:8000/agent/chat \
	-H 'content-type: application/json' \
	-d '{"message":"hello agent","label":"M0"}'
```

Smoke script
------------

There's a small smoke script that starts the app (using the PORT env var or
defaulting to 8080) and POSTs a test message to `/agent/chat`:

Run locally:

```bash
PYTHONPATH=. python3 scripts/smoke_agent_post.py
```

This prints the HTTP status and JSON response. If you want DB-backed
behavior, set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in your environment
before running.

Codespaces / Port forwarding note
--------------------------------

When running in GitHub Codespaces you typically want the app reachable on the
public forwarded port. Historically this project used port 8080 — to match
that behavior the application will respect the `PORT` environment variable and
default to `8080`. If you open a Codespace and want to view the running site,
ensure port 8080 is marked Public (or forwarded) in the Codespaces Ports panel.

CI / GitHub Actions
-------------------

The repository contains a lightweight CI workflow at
`.github/workflows/ci.yml` which installs the dependencies and runs the test
suite with `PYTHONPATH=.`. If you want to enable DB-backed end-to-end checks
in CI, add `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to the repository
secrets; the workflow will inject them into the test run.

Integration tests (LangGraph + OpenAI)
-------------------------------------
If you want to run integration tests that exercise the real LangGraph + OpenAI agent locally, do the following:

1. Ensure you have a valid OpenAI API key available.

2. Export the environment variables:

```bash
export OPENAI_API_KEY="sk-..."
export AGENT_USE_LANGGRAPH=1
```

3. Run only integration tests (those marked with pytest.mark.integration):

```bash
PYTHONPATH=. AGENT_USE_LANGGRAPH=1 pytest -q -m integration
```

CI note: the repository workflow contains an optional `integration` job that runs these tests when you set the repository secret `LANGGRAPH_ENABLED` and `OPENAI_API_KEY`.

