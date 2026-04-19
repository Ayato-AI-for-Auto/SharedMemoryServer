import pytest

from shared_memory.logic import save_memory_core
from shared_memory.search import perform_keyword_search, perform_search


@pytest.mark.asyncio
async def test_search_scoring_logic_unit(fake_llm):
    """
    Unit test: Verify hybrid scoring and ranking.
    - Semantic match (via FakeGeminiClient deterministic vectors)
    - Importance boost
    """
    # 1. Seed two items
    # High Importance Item
    await save_memory_core(
        entities=[{"name": "Apple", "description": "A very important fruit", "importance": 10}],
        agent_id="test",
    )
    # Low Importance Item
    await save_memory_core(
        entities=[{"name": "Banana", "description": "A low priority fruit", "importance": 1}],
        agent_id="test",
    )

    # 2. Search for 'fruit'
    # Since both have 'fruit' in description, both will have semantic matches.
    # Apple should rank higher due to importance score (30% weight in hybrid).
    graph_data, _ = await perform_search("fruit")

    entity_names = [e["name"] for e in graph_data["entities"]]
    assert entity_names[0] == "Apple"
    assert entity_names[1] == "Banana"


@pytest.mark.asyncio
async def test_keyword_search_ranking_unit():
    """Verify keyword search priority (ID match > Content match)."""
    await save_memory_core(
        entities=[{"name": "Database", "description": "Storing data"}],
        observations=[{"entity_name": "SomethingElse", "content": "Database mentioned here"}],
    )

    # Searching for 'Database'
    results = await perform_keyword_search("Database")

    # The 'entities' ID match should rank first (Score 10.0 vs ~1.5)
    assert results[0]["id"] == "Database"
    assert results[0]["source"] == "entities"
    assert results[1]["source"] == "observations"


@pytest.mark.asyncio
async def test_importance_calculation_unit():
    """Verify the math behind importance/relevance score."""
    import datetime

    from shared_memory.utils import calculate_importance

    # Case 1: Moderate frequency, recent (Now)
    now = datetime.datetime.now().isoformat()
    recent_score = calculate_importance(10, now)

    # Case 2: High frequency, but very old (1 year ago)
    # The exponential decay (30-day half-life) should dominate
    old = (datetime.datetime.now() - datetime.timedelta(days=365)).isoformat()
    old_score = calculate_importance(100, old)

    # Recent (even with lower count) should be higher than a year-old item
    assert recent_score > old_score
    assert recent_score >= 0.0
    assert old_score >= 0.0
