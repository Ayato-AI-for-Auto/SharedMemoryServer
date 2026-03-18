import pytest
from unittest.mock import MagicMock
from shared_memory.server import (
    save_memory,
    get_memory_map,
    synthesize_knowledge,
    get_conflicts,
)
from shared_memory.database import init_db


@pytest.mark.asyncio
async def test_memory_map(mock_gemini):
    init_db()
    await save_memory(
        entities=[
            {"name": "A", "entity_type": "Node"},
            {"name": "B", "entity_type": "Node"},
        ],
        relations=[{"source": "A", "target": "B", "relation_type": "connects"}],
    )

    mermaid = await get_memory_map()
    assert "graph TD" in mermaid
    assert '"A" -- connects --> "B"' in mermaid


@pytest.mark.asyncio
async def test_synthesize_knowledge(mock_gemini):
    init_db()
    # Mock for synthesize_knowledge
    mock_gemini.models.generate_content.return_value = MagicMock(
        text="Synthesized info about Python."
    )

    await save_memory(
        entities=[{"name": "Python", "entity_type": "Language"}],
        observations=[{"entity_name": "Python", "content": "Popular for AI"}],
    )

    summary = await synthesize_knowledge("Python")
    assert "### Knowledge Synthesis: Python" in summary
    assert "Synthesized info about Python." in summary


@pytest.mark.asyncio
async def test_conflict_detection(mock_gemini):
    init_db()

    # 1. Save initial knowledge
    await save_memory(
        entities=[{"name": "Status", "entity_type": "State"}],
        observations=[{"entity_name": "Status", "content": "The system is ONLINE."}],
    )

    # 2. Mock Gemini to detect a conflict
    # We need to simulate the JSON response from _check_conflict
    mock_gemini.models.generate_content.return_value = MagicMock(
        text='{"conflict": true, "reason": "New info says OFFLINE while old says ONLINE"}'
    )

    # 3. Save conflicting knowledge
    res = await save_memory(
        observations=[{"entity_name": "Status", "content": "The system is OFFLINE."}]
    )

    # 4. Verify conflict was reported and stored
    assert "conflicts_detected" in res
    assert res["conflicts_detected"][0]["entity"] == "Status"

    conflicts = get_conflicts("Status")
    assert len(conflicts) == 1
    assert conflicts[0]["new"] == "The system is OFFLINE."
    assert "OFFLINE" in conflicts[0]["reason"]
