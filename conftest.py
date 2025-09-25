import os
import pytest


def pytest_collection_modifyitems(config, items):
    """Skip tests marked 'integration' unless AGENT_USE_LANGGRAPH is enabled.

    This lets CI or local developers opt in to the slower, networked
    LangGraph/OpenAI-backed integration tests by setting AGENT_USE_LANGGRAPH=1.
    """
    if os.getenv("AGENT_USE_LANGGRAPH", "").lower() in ("1", "true", "yes"):
        return

    skip_integration = pytest.mark.skip(reason="integration tests disabled; set AGENT_USE_LANGGRAPH=1 to enable")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
