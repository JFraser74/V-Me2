Railway Deploy Checklist

1) Variables (Railway -> Variables):
   • SUPABASE_URL
   • SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY for read-only)
   • OPENAI_API_KEY (optional)

2) Start command / Procfile:
   Ensure the project has a Procfile containing:

   web: python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}

3) Re-deploy and check logs for a successful startup. If you see "ModuleNotFoundError: routes.agent" ensure `routes/__init__.py` exists.

4) Railway Shell quick test (paste into Railway Shell after deployment):

   curl -fsS http://127.0.0.1:${PORT}/health && \
   curl -fsS http://127.0.0.1:${PORT}/showme | head -n 5 && \
   curl -fsS -X POST http://127.0.0.1:${PORT}/agent/chat -H 'content-type: application/json' -d '{"message":"hello from railway","label":"railway"}'

If the last call returns an echo, the app is live. If OPENAI_API_KEY is set, you'll get LLM responses.
