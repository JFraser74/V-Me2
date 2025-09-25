#!/usr/bin/env python3
"""Simple test runner for va_graph filter behavior and health checks.

Usage: python scripts/va_langgraph_test.py
"""
import os
import json
from typing import Any, Dict, List

from fastapi.testclient import TestClient
import main


def run_health_check() -> Dict[str, Any]:
    c = TestClient(main.app)
    h = c.get("/health")
    return {"status_code": h.status_code, "text": h.text}


def run_chat_test(message: str) -> Dict[str, Any]:
    c = TestClient(main.app)
    r = c.post("/agent/chat", json={"message": message, "label": "va-langgraph-test"})
    try:
        body = r.json()
    except Exception:
        body = {"text": r.text}
    return {"status_code": r.status_code, "body": body}


def probe_filter():
    # Import the module and exercise filter function if available
    try:
        from graph import va_graph
        msgs_in = [
            {"role": "user", "content": "List files"},
            {"role": "assistant", "content": "Calling ls", "tool_calls": [{"id":"1","name":"ls"}]},
            {"role": "tool", "content": "file1\nfile2"},
            {"role": "tool", "content": "orphan tool message"},
        ]
        filtered = va_graph._filter_tool_sequence(msgs_in)
        return {"available": True, "input_count": len(msgs_in), "output_count": len(filtered), "filtered": filtered}
    except Exception as e:
        return {"available": False, "error": str(e)}


def main_run():
    print("va_langgraph_test: starting")
    print("AGENT_TOOLS_ENABLED:", os.getenv("AGENT_TOOLS_ENABLED", "1"))
    print("AGENT_USE_LANGGRAPH:", os.getenv("AGENT_USE_LANGGRAPH", "0"))
    print("OPENAI_MODEL:", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    print(json.dumps(run_health_check(), indent=2))
    print("-- plain chat --")
    print(json.dumps(run_chat_test("ping"), indent=2))
    print("-- tool chat --")
    print(json.dumps(run_chat_test("Use the ls tool to list project files and summarize."), indent=2))
    print("-- filter probe --")
    print(json.dumps(probe_filter(), indent=2))
    # quick ls probe
    try:
        c = TestClient(main.app)
        r = c.get('/agent/ls?path=.')
        print('-- ls probe --')
        try:
            print(json.dumps(r.json(), indent=2))
        except Exception:
            print(r.text)
    except Exception as e:
        print('ls probe failed', e)

    # tool_events round-trip (best-effort): create a session, log a tool event, fetch it
    try:
        c = TestClient(main.app)
        r = c.post('/agent/chat', json={'message': 'probe tool events', 'label': 'va-langgraph-test'})
        sid = None
        try: sid = r.json().get('session_id')
        except Exception: sid = None
        print('-- created session:', sid)
        if sid:
            # Try to fetch tool events (may be empty)
            te = c.get(f'/agent/tool_events?session_id={sid}&limit=5')
            print('-- tool_events --')
            try:
                print(json.dumps(te.json(), indent=2))
            except Exception:
                print(te.text)
    except Exception as e:
        print('tool_events probe failed', e)


if __name__ == "__main__":
    main_run()
