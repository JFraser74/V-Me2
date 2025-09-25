import pytest

from graph import va_graph


@pytest.mark.skipif(not va_graph._LG_OK, reason="langgraph types unavailable")
def test_filter_keeps_tool_after_ai_tool_call():
    ai = va_graph.AIMessage(content="do something")
    # attach tool_calls metadata the filter looks for
    setattr(ai, "tool_calls", [{"id": "tc1", "name": "ls", "args": {}}])
    # ToolMessage requires a tool_call_id at construction
    tm = va_graph.ToolMessage(tool_call_id="tc1", content="file1\nfile2")
    inp = [ai, tm]
    out = va_graph._filter_tool_sequence(inp)
    assert out == [ai, tm]


@pytest.mark.skipif(not va_graph._LG_OK, reason="langgraph types unavailable")
def test_filter_drops_orphan_tool_message():
    # Provide a tool_call_id but no preceding AIMessage with tool_calls -> should be dropped
    tm = va_graph.ToolMessage(tool_call_id="orphan_id", content="orphan")
    inp = [tm]
    out = va_graph._filter_tool_sequence(inp)
    assert out == []
