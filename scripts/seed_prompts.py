#!/usr/bin/env python3
"""
Idempotent seeding helper for V-Me2 prompts.

Usage:
  # Generate SQL files only
  python3 scripts/seed_prompts.py --gen-sql

  # Run SQL via psql if DATABASE_URL is available in env
  DATABASE_URL=postgres://... python3 scripts/seed_prompts.py --run

The script extracts the persona and system prompts from `docs/AGENT_PROMPTS.md`
and writes two SQL files: `scripts/seed_persona.sql` and `scripts/seed_session.sql`.

It will NOT attempt to push secrets to the repo. If you set DATABASE_URL, it will try
to execute the generated SQL using `psql` (must be available on PATH).
"""
import os
import re
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs' / 'AGENT_PROMPTS.md'
OUT_DIR = ROOT / 'scripts'
OUT_DIR.mkdir(exist_ok=True)


def extract_code_block(md_text, heading_title):
    # Find the heading and then the first ```text block after it
    idx = md_text.find(heading_title)
    if idx < 0:
        return None
    sub = md_text[idx:]
    m = re.search(r"```text\n(.*?)\n```", sub, flags=re.S)
    return m.group(1).strip() if m else None


def generate_persona_sql(persona_text: str) -> str:
    return f"""
-- Upsert persona prompt into va_settings as jsonb text
INSERT INTO public.va_settings (key, value)
VALUES (
  'persona_prompt',
  to_jsonb($${persona_text}$$::text)
)
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
"""


def generate_session_sql(system_text: str, user_text: str) -> str:
    # Idempotent: find existing session by label 'agent-boot' or create it. Then insert system and user messages only if missing.
    return f"""
-- Create or find agent-boot session and insert system + initial user messages (idempotent)
WITH existing AS (
  SELECT id FROM public.va_sessions WHERE label = 'agent-boot' LIMIT 1
), ins AS (
  INSERT INTO public.va_sessions (label, created_at)
  SELECT 'agent-boot', now()
  WHERE NOT EXISTS (SELECT 1 FROM existing)
  RETURNING id
), session_id AS (
  SELECT id FROM ins
  UNION ALL
  SELECT id FROM existing
)
-- Insert system message if not already present
INSERT INTO public.va_messages (session_id, role, content, created_at)
SELECT id, 'system', $${system_text}$$, now() FROM session_id
WHERE NOT EXISTS (
  SELECT 1 FROM public.va_messages m WHERE m.session_id = (SELECT id FROM session_id) AND m.role = 'system' AND m.content LIKE 'SYSTEM: V-Me2 runtime%'
);

-- Insert initial user message if not present
INSERT INTO public.va_messages (session_id, role, content, created_at)
SELECT id, 'user', $${user_text}$$, now() FROM session_id
WHERE NOT EXISTS (
  SELECT 1 FROM public.va_messages m WHERE m.session_id = (SELECT id FROM session_id) AND m.role = 'user' AND m.content LIKE 'Hi — read the system message%'
);

-- Return the session id and any newly inserted message ids (psql will display results if run interactively)
SELECT id AS session_id FROM session_id;
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gen-sql', action='store_true', help='Generate SQL files and exit')
    parser.add_argument('--run', action='store_true', help='Run generated SQL with psql (requires DATABASE_URL env var and psql on PATH)')
    args = parser.parse_args()

    md = DOCS.read_text(encoding='utf-8')
    persona = extract_code_block(md, '## Persona / System Prompt (seed into `va_settings.persona_prompt`)')
    system = extract_code_block(md, '## Coding / System prompt (seed into a session\'s system message)')
    if not persona or not system:
        print('Failed to extract prompts from docs/AGENT_PROMPTS.md; please verify the file contains the expected code blocks.')
        return 1

    # For the initial user message we use a short, safe prompt
    user_text = "Hi — read the system message for this session, then list the top 3 immediate next steps to help connect the Supabase Gmail copy to the email queue. Keep each step one line and flag any missing credentials, table names, or env vars required. Do not perform writes."

    persona_sql = generate_persona_sql(persona)
    session_sql = generate_session_sql(system, user_text)

    persona_path = OUT_DIR / 'seed_persona.sql'
    session_path = OUT_DIR / 'seed_session.sql'
    persona_path.write_text(persona_sql, encoding='utf-8')
    session_path.write_text(session_sql, encoding='utf-8')

    print(f'Wrote: {persona_path}\nWrote: {session_path}')

    if args.run:
        db = os.environ.get('DATABASE_URL')
        if not db:
            print('DATABASE_URL not set; cannot run SQL. Exiting.')
            return 2
        # Try to run both SQL files using psql
        for p in [persona_path, session_path]:
            print('Running', p)
            try:
                subprocess.check_call(['psql', db, '-f', str(p)])
            except subprocess.CalledProcessError as e:
                print('psql failed:', e)
                return 3

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
