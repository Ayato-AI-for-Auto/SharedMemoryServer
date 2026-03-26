import pytest
import os
from shared_memory import server, thought_logic, database
from shared_memory.thought_logic import get_thought_history


@pytest.fixture(autouse=True)
def init_test_dbs(mock_env):
    """Initializes both knowledge and thoughts databases for each test."""
    database.init_db()
    thought_logic.init_thoughts_db()
    yield


@pytest.mark.asyncio
async def test_sequential_thinking_tool_integration():
    """
    Tests the sequential_thinking tool integration within the FastMCP server.
    Ensures that the tool is registered and can be called.
    """
    # Simulate tool call via the mcp instance
    # Note: FastMCP tools are async functions
    result = await server.sequential_thinking(
        thought="Thinking about adding a new entity",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id="integration_session",
    )

    assert result["thoughtNumber"] == 1
    assert result["nextThoughtNeeded"] is True

    # Verify persistence
    history = await get_thought_history("integration_session")
    assert len(history) == 1
    assert history[0]["thought"] == "Thinking about adding a new entity"


@pytest.mark.asyncio
async def test_thought_and_memory_coexistence():
    """
    Tests that thought processing and memory saving can coexist without conflict.
    """
    # 1. Start thinking
    await server.sequential_thinking(
        thought="I will save an entity now",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id="coexist_session",
    )

    # 2. Save memory (using existing stable logic)
    # We use logic.save_memory_core directly or via server tool
    await server.save_memory(
        entities=[{"name": "CoexistEntity", "entity_type": "Test", "description": "Testing coexistence"}]
    )

    # 3. Finish thinking
    await server.sequential_thinking(
        thought="Entity saved successfully",
        thought_number=2,
        total_thoughts=2,
        next_thought_needed=False,
        session_id="coexist_session",
    )

    # 4. Verify both exist
    history = await get_thought_history("coexist_session")
    assert len(history) == 2
    
    # Check graph memory
    graph_data = await server.get_graph_data(query="CoexistEntity")
    assert any(e["name"] == "CoexistEntity" for e in graph_data["entities"])
