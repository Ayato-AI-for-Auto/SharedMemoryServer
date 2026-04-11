import pytest

from shared_memory.insights import InsightEngine
from shared_memory.logic import read_memory_core, save_memory_core


@pytest.mark.asyncio
async def test_search_to_insight_integration():
    """
    Integration test: save -> search -> verify hit rate in insights.
    Checks the flow between memory utilization and its quantification.
    """
    # 1. Save dummy knowledge
    print("\n--- Diagnostic: Starting Step 1 (Save)")
    await save_memory_core(
        entities=[{
            "name": "Python",
            "entity_type": "language",
            "description": "A coding language"
        }]
    )
    print("--- Diagnostic: Step 1 (Save) Complete")

    # 2. Perform searches (1 hit)
    print("--- Diagnostic: Starting Step 2a (Search Hit)")
    await read_memory_core(query="Python")
    print("--- Diagnostic: Step 2a (Search Hit) Complete")

    # Perform a query that definitely misses (0 results)
    print("--- Diagnostic: Starting Step 2b (Search Miss)")
    await read_memory_core(query="ZyzygyNonExistentWord123")
    print("--- Diagnostic: Step 2b (Search Miss) Complete")

    # 3. Verify through InsightEngine
    print("--- Diagnostic: Starting Step 3 (Insights)")
    metrics = await InsightEngine.get_summary_metrics()
    print("--- Diagnostic: Step 3 (Insights) Complete")
    f = metrics["facts"]

    assert f["total_search_queries"] == 2
    # Expecting 1 hit out of 2 queries
    assert f["search_hit_rate_percent"] == 50.0

@pytest.mark.asyncio
async def test_multi_access_reuse_multiplier():
    """
    Integration test: multiple reads of the same entity increase reuse multiplier.
    """
    await save_memory_core(
        entities=[{
            "name": "ToolA",
            "entity_type": "tool",
            "description": "Useful tool"
        }]
    )

    # Access ToolA twice via search.
    # Search for "ToolA" should find it and update_access via search logic.
    await read_memory_core(query="ToolA")
    await read_memory_core(query="ToolA")

    metrics = await InsightEngine.get_summary_metrics()
    i = metrics["efficiency_indicators"]

    # Total access should be 2, items 1 -> 2.0x
    assert i["reuse_multiplier"] >= 2.0
