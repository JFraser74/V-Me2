from fastapi.testclient import TestClient
import pytest

from main import app


def test_agent_chat_logs_user_and_assistant(monkeypatch):
    calls = []

    def fake_safe_log_message(session_id, role, content):
        calls.append((session_id, role, content))

    import routes.agent as agent_mod
    monkeypatch.setattr(agent_mod, "safe_log_message", fake_safe_log_message)

    # Ensure we run the non-fake path so user logging occurs
    monkeypatch.delenv("DEV_LOCAL_LLM", raising=False)

    class FakeGraph:
        def invoke(self, state_in, config=None):
            return {"last_text": "(fake reply)", "tool_events": []}

    monkeypatch.setattr(agent_mod, "get_graph", lambda: FakeGraph())
    # Ensure a session id is created so user logging runs
    monkeypatch.setattr(agent_mod, "create_session", lambda label=None: 999)

    client = TestClient(app)
    r = client.post("/agent/chat", json={"message": "hello world"})
    assert r.status_code == 200
    # Expect at least two log calls: user then assistant
    roles = [c[1] for c in calls]
    assert "user" in roles
    assert "assistant" in roles
