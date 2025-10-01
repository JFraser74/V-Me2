#!/usr/bin/env python3
"""Seed two foundational memory rows into Supabase (va_sessions + va_messages).

This script is idempotent: it will search for a session with the given label and
use it if found; otherwise it creates a new session. Then it inserts a single
message row for each session using safe_log_message().

Run: python3 scripts/seed_supabase_memory.py
"""
import sys
from vme_lib import supabase_client as sb


def find_session_by_label(label: str):
    cli = sb._client()
    if not cli:
        return None
    try:
        res = cli.table('va_sessions').select('*').eq('label', label).limit(1).execute()
        rows = getattr(res, 'data', None) or []
        if rows:
            return rows[0].get('id')
    except Exception:
        return None
    return None


def ensure_session(label: str):
    sid = find_session_by_label(label)
    if sid:
        print(f"Found existing session '{label}' -> id={sid}")
        return sid
    print(f"Creating session '{label}'...")
    sid = sb.create_session(label=label)
    if not sid:
        print("Failed to create session: supabase client not configured or insert failed.")
        return None
    print(f"Created session id={sid}")
    return sid


def main():
    # Session A
    label_a = "System Setup & Current Status — M0"
    content_a = """
VME2_STATUS_V1
build: Railway main (no-store hot asset active)
ui: Coding panel with streaming SSE, Save & Name, Admin mode link, Ops viewer
ops: In-app orchestrator live (create/list/get/cancel + tokenized SSE), DEV_LOCAL_LLM=fake supported
voice: Fake-mode upload + mic UI merged; real Whisper gated by OPENAI_API_KEY & toggle
meeting: Fake-mode scaffold + write-only Supabase wiring
memory: va_sessions/va_messages live; threads API + Save & Name UI
security: SETTINGS_ADMIN_TOKEN/CI_SETTINGS_ADMIN_TOKEN; OPS_STREAM_SECRET for SSE; confirm=True for write tools
ci: deterministic flags supported; smoke workflow exists (manual dispatch by admin)
next: planner hand-off live (/agent/plan); attachments placeholder; SSE tokens
""".strip()

    # Session B
    label_b = "Agent Personality & Operating Principles"
    content_b = """
PLACEHOLDER: Agent Personality & Operating Principles

This is a system-level personality prompt for the in-app assistant. Replace this
placeholder with the real system prompt when you have it. For now this row
establishes the memory slot and will be used by the agent as baseline context.
""".strip()

    sid_a = ensure_session(label_a)
    sid_b = ensure_session(label_b)

    if not sid_a and not sid_b:
        print("No sessions available; check SUPABASE_URL and service key in the environment.")
        sys.exit(2)

    if sid_a:
        print(f"Inserting assistant message into session id={sid_a}...")
        sb.safe_log_message(sid_a, 'assistant', content_a)
        print("Inserted message for Session A.")

    if sid_b:
        print(f"Inserting system message into session id={sid_b}...")
        sb.safe_log_message(sid_b, 'system', content_b)
        print("Inserted message for Session B.")

    print("Done. Verify in Supabase or via the app's threads/messages API.")


if __name__ == '__main__':
    main()
