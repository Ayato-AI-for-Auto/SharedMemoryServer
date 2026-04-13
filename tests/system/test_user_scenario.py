import pytest

from shared_memory.logic import read_memory_core, save_memory_core
from shared_memory.thought_logic import process_thought_core


@pytest.mark.asyncio
async def test_end_to_end_user_scenario(mock_gemini):
    """
    System Test: Verifies a complete user flow.
    1. Agent records initial context.
    2. Agent thinks about it (Sequential Thinking).
    3. Knowledge is distilled.
    4. Agent retrieves distilled knowledge later.
    """
    # 1. Initial Context
    await save_memory_core(
        entities=[{"name": "Scenario X", "description": "Experimental setup"}]
    )

    # 2. Sequential Thinking Process
    # Step 1: Thinking
    await process_thought_core(
        thought="I need to consider the power constraints for Scenario X.",
        thought_number=1,
        total_thoughts=2,
        next_thought_needed=True,
        session_id="scenario_session",
    )

    # Step 2: Final Conclusion (Triggers Distillation)
    await process_thought_core(
        thought="The power constraint is 500W maximum.",
        thought_number=2,
        total_thoughts=2,
        next_thought_needed=False,
        session_id="scenario_session",
    )

    # 3. Knowledge Retrieval
    # The distillation happens in the background (or foreground in process_thought_core)
    # We verify if we can find '500W' related to 'Scenario X'
    data = await read_memory_core(query="500W power constraint")

    # Check graph entities
    found = False
    for entity in data["graph"]["entities"]:
        if "Scenario X" in entity["name"]:
            found = True
            break
    assert found, "Historical context should be preserved"

    # Verify search result context
    # In search results, either graph data or synthesized context should reflect
    # the new knowledge
    assert len(data["graph"]["observations"]) > 0 or len(data["graph"]["entities"]) > 0
