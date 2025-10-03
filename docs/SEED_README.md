## Seeding agent prompts (persona + boot session)

This repository includes two ready-to-run artifacts to seed the V-Me2 assistant prompts into Supabase/Postgres:

- `docs/AGENT_PROMPTS.md` — contains the persona prompt and the system prompt (human-readable and ready to paste into SQL).
- `scripts/seed_prompts.py` — an idempotent helper that extracts prompts from `docs/AGENT_PROMPTS.md` and writes `scripts/seed_persona.sql` and `scripts/seed_session.sql`. It can optionally run them using `psql` if `DATABASE_URL` is provided.

Quick steps

1. Generate SQL files locally (no secrets required):

```bash
python3 scripts/seed_prompts.py --gen-sql
# created: scripts/seed_persona.sql, scripts/seed_session.sql
```

2. Inspect the generated SQL files. If you want to run them from your machine:

```bash
# ensure psql is installed and DATABASE_URL is set to a trusted service role URL
DATABASE_URL=postgres://... python3 scripts/seed_prompts.py --run
```

3. Alternatively, paste the generated SQL into Supabase SQL editor and run manually.

Security note

- The script does not embed secrets in the repo. When executing against your DB, use a trusted environment variable (`DATABASE_URL`) or run SQL from Supabase's SQL editor.
- Do not commit service role keys to the repository.

What the seed does

- Upserts `persona_prompt` into `public.va_settings` as jsonb text.
- Creates (or finds) a session labeled `agent-boot` and inserts the system prompt and a safe initial user message (read-only task instruction).
- You can change the initial user message by editing `scripts/seed_prompts.py` before running `--gen-sql`.

If you want, I can open a PR with these files on `hotfix/manual-edits-20251001` and create the PR for you to review (so seeding is auditable). Say “open PR” and I will push a branch and create the PR. 
