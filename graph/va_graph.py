"""Guarded ReAct adapter for V-Me2.

Provides a minimal, defensive wrapper around LangGraph + ChatOpenAI.
If optional dependencies are missing the module falls back to an echo
responder so the rest of the app and tests can run in local development.
"""

from __future__ import annotations
import os
import sys
try:
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _PROJECT_ROOT and _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
except Exception:
    pass
import os
from typing import Any, Dict, List, TypedDict, TYPE_CHECKING
from vme_lib.supabase_client import settings_get

if TYPE_CHECKING:
    from langgraph.prebuilt import create_react_agent  # type: ignore
    from langchain_openai import ChatOpenAI  # type: ignore
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage  # type: ignore


try:
    from langgraph.prebuilt import create_react_agent
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
    _LG_OK = True
except Exception:
    _LG_OK = False


# Optional tools (modules are defensive)
try:
    from tools.codespace import (
        ls_tool,
        read_file_tool,
        write_file_tool,
        git_status_tool,
        git_diff_tool,
        git_commit_tool,
    )
    from tools.supabase_tools import sb_select_tool, sb_upsert_tool
    _TOOLS_OK = True
except Exception:
    _TOOLS_OK = False


class AgentState(TypedDict):
    session_id: str
    messages: List[Dict[str, Any]]
    remaining_steps: int


def _filter_tool_sequence(messages: List[Any]) -> List[Any]:
    """Drop any ToolMessage that isn't immediately preceded by an AIMessage
    containing tool_calls. This prevents illegal payloads from reaching
    the OpenAI chat API (which rejects role='tool' messages outside of a
    proper tool_call flow).
    """
    if not messages:
        return messages
    out: List[Any] = []
    prev_ai_had_tool_calls = False
    for m in messages:
        try:
            if _LG_OK and isinstance(m, AIMessage):
                prev_ai_had_tool_calls = bool(getattr(m, "tool_calls", None))
                out.append(m)
            elif _LG_OK and isinstance(m, ToolMessage):
                if prev_ai_had_tool_calls:
                    out.append(m)
            else:
                out.append(m)
                prev_ai_had_tool_calls = False
        except Exception:
            out.append(m)
            prev_ai_had_tool_calls = False
    return out


class GuardedChatOpenAI:
    """Adapter that filters tool-message sequences before delegating to
    the real ChatOpenAI. If ChatOpenAI can't be constructed the adapter
    provides a safe fallback shape for local tests.
    """

    def __init__(self, *args, **kwargs):
        try:
            self._inner = ChatOpenAI(*args, **kwargs)
        except Exception:
            self._inner = None

    def invoke(self, input, config=None, **kwargs):
        try:
            if isinstance(input, dict) and "messages" in input:
                input = dict(input)
                input["messages"] = _filter_tool_sequence(input["messages"])
            elif isinstance(input, list):
                input = _filter_tool_sequence(input)
        except Exception:
            pass

        if self._inner:
            return self._inner.invoke(input, config=config, **kwargs)
        return {"messages": input}

    def bind_tools(self, tool_classes: list):
        """Called by LangGraph to attach tools to the model. We delegate to
        the inner model when possible; otherwise record the binding and
        return self so LangGraph can continue.
        """
        if self._inner and hasattr(self._inner, "bind_tools"):
            return self._inner.bind_tools(tool_classes)
        # record for debugging; no-op otherwise
        self._bound_tools = tool_classes
        return self

    def __getattr__(self, name: str):
        # Delegate unknown attributes to the inner model when present.
        inner = object.__getattribute__(self, "_inner")
        if inner and hasattr(inner, name):
            return getattr(inner, name)
        raise AttributeError(name)


def _build_graph():
    # Only build the real graph when langgraph + an API key are available
    # and the feature is explicitly enabled via AGENT_USE_LANGGRAPH.
    # This avoids accidental external API calls during tests or local runs.
    if not (_LG_OK and os.getenv("OPENAI_API_KEY") and os.getenv("AGENT_USE_LANGGRAPH", "0") in ("1", "true", "yes")):
        return None

    tools = []
    _tools_enabled_val = settings_get("AGENT_TOOLS_ENABLED", os.getenv("AGENT_TOOLS_ENABLED", "1"))
    tools_enabled = str(_tools_enabled_val).lower() not in ("0", "false", "False", "no", "off")
    if _TOOLS_OK and tools_enabled:
        tools = [
            ls_tool,
            read_file_tool,
            write_file_tool,
            git_status_tool,
            git_diff_tool,
            git_commit_tool,
            # add git_push_tool so the agent can push when explicitly confirmed
            getattr(globals().get('git_push_tool', None), '__call__', None) or None,
            sb_select_tool,
            sb_upsert_tool,
        ]

    _model = settings_get("OPENAI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    _api_key = settings_get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"), decrypt=True)
    llm = GuardedChatOpenAI(model=_model, temperature=0, api_key=_api_key)
    return create_react_agent(llm, tools, state_schema=AgentState)


class _Wrapper:
    """Stable wrapper exposing invoke(state, config) and handling fallbacks."""

    def __init__(self):
        self._graph = _build_graph()

    def _to_lc_messages(self, items: List[Dict[str, Any]]):
        if not _LG_OK:
            return items
        out = []
        for m in items:
            role = m.get("role", "user")
            content = m.get("content", "")
            # Never forward persisted 'tool' messages as chat messages.
            if role == "tool":
                continue
            if role == "user":
                out.append(HumanMessage(content=content))
            elif role == "assistant":
                out.append(AIMessage(content=content))
            else:
                out.append(SystemMessage(content=content))
        return out

    def invoke(self, state: Dict[str, Any], config: Dict[str, Any] | None = None) -> Dict[str, Any]:
        # Echo fallback when the graph isn't available
        if self._graph is None:
            msgs = state.get("messages", [])
            last = msgs[-1]["content"] if msgs else ""
            return {"last_text": f"Echo: {last}", "session_id": state.get("session_id", "")}

        msgs = [m for m in state.get("messages", []) if m.get("role") != "tool"]
        res = self._graph.invoke({"session_id": state.get("session_id", ""), "messages": self._to_lc_messages(msgs)}, config=config)

        last_text = ""
        tool_events: List[Dict[str, Any]] = []
        try:
            call_inputs: Dict[str, Dict[str, Any]] = {}
            for m in res.get("messages", []) or []:
                if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
                    for tc in m.tool_calls:
                        call_inputs[tc.get("id")] = {"tool_name": tc.get("name"), "input_json": tc.get("args")}

            for m in reversed(res.get("messages", []) or []):
                if isinstance(m, AIMessage):
                    last_text = getattr(m, "content", "")
                    break

            for m in res.get("messages", []) or []:
                if _LG_OK and isinstance(m, ToolMessage):
                    tcid = getattr(m, "tool_call_id", None)
                    entry: Dict[str, Any] = {
                        "tool_name": None,
                        "input_json": None,
                        "output_json": getattr(m, "content", None),
                    }
                    if tcid and tcid in call_inputs:
                        entry["tool_name"] = call_inputs[tcid].get("tool_name")
                        entry["input_json"] = call_inputs[tcid].get("input_json")
                    tool_events.append(entry)
        except Exception:
            msgs = state.get("messages", [])
            last = msgs[-1]["content"] if msgs else ""
            last_text = f"Echo: {last}"

        return {"last_text": last_text, "session_id": state.get("session_id", ""), "tool_events": tool_events}


_singleton = _Wrapper()


def get_graph():
    return _singleton
