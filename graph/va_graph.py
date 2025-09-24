"""LangGraph M0: ReAct agent bootstrap with safe fallbacks.

This file implements the M0 LangGraph bootstrap described in the Canvas
attachment. Behavior:
 - If langgraph, langchain_openai, and OPENAI_API_KEY are available, build
   a minimal ReAct-style agent using prebuilt helpers and available tools.
 - If any dependency or env var is missing, fall back to an echoing stub so
   the /agent/chat route remains functional for local development.
"""

from __future__ import annotations
import os
from typing import Any, Dict, TypedDict, List, TYPE_CHECKING

# Optional imports — the agent will gracefully fall back if missing
# When running static analysis (TYPE_CHECKING), import symbols so linters
# and type checkers can resolve names. At runtime we keep the same try/except
# behavior so the module is safe when optional deps are not installed.
if TYPE_CHECKING:
    # These imports are only for type checkers and editor language servers.
    from langgraph.prebuilt import create_react_agent  # type: ignore
    from langchain_openai import ChatOpenAI  # type: ignore
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage  # type: ignore
    from langgraph.graph import MessagesState  # type: ignore

try:
    from langgraph.prebuilt import create_react_agent
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langgraph.graph import MessagesState
    _LG_OK = True
except Exception:
    _LG_OK = False

# Tools (each module internally handles missing deps / env)
try:
    from tools.codespace import ls_tool, read_file_tool, write_file_tool, git_status_tool, git_diff_tool, git_commit_tool
    from tools.supabase_tools import sb_select_tool, sb_upsert_tool
    _TOOLS_OK = True
except Exception:
    _TOOLS_OK = False


class AgentState(TypedDict):
    # Use simple, runtime-friendly annotations. LangGraph will inspect these
    # types when building the state schema; avoid using Annotated with
    # runtime-only metadata objects here (they can be present under
    # TYPE_CHECKING for editors).
    session_id: str
    messages: List[Dict[str, Any]]
    remaining_steps: int


def _build_graph():
    """Build a ReAct agent graph when deps + OPENAI_API_KEY are available."""
    if not (_LG_OK and os.getenv("OPENAI_API_KEY")):
        return None

    tools = []
    if _TOOLS_OK:
        tools = [
            ls_tool,
            read_file_tool,
            write_file_tool,
            git_status_tool,
            git_diff_tool,
            git_commit_tool,
            sb_select_tool,
            sb_upsert_tool,
        ]

    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
    return create_react_agent(llm, tools, state_schema=AgentState)


class _Wrapper:
    """Adds a stable `.invoke(state, config)` API and handles fallbacks."""
    def __init__(self):
        self._graph = _build_graph()

    def _to_lc_messages(self, items: List[Dict[str, Any]]):
        if not _LG_OK:
            return items
        out = []
        for m in items:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "user":
                out.append(HumanMessage(content=content))
            elif role == "assistant":
                out.append(AIMessage(content=content))
            else:
                out.append(SystemMessage(content=content))
        return out

    def invoke(self, state: Dict[str, Any], config: Dict[str, Any] | None = None) -> Dict[str, Any]:
        # Fallback: echo
        if self._graph is None:
            msgs = state.get("messages", [])
            last = msgs[-1]["content"] if msgs else ""
            return {"last_text": f"Echo: {last}", "session_id": state.get("session_id", "")}

        # Convert messages and call graph
        msgs = state.get("messages", [])
        res = self._graph.invoke({"session_id": state.get("session_id", ""), "messages": self._to_lc_messages(msgs)}, config=config)

        # Extract last assistant message text
        last_text = ""
        try:
            for m in reversed(res["messages"]):
                if isinstance(m, AIMessage):
                    last_text = m.content
                    break
        except Exception:
            # In case of unexpected structure, retain echo-style resilience
            last = msgs[-1]["content"] if msgs else ""
            last_text = f"Echo: {last}"

        return {"last_text": last_text, "session_id": state.get("session_id", "")}


_singleton = _Wrapper()


def get_graph():
    return _singleton
