from unittest.mock import MagicMock
import pytest
from shared_memory.server import (
    save_memory,
    read_memory,
    delete_memory,
    get_audit_history,
    get_memory_health,
    create_snapshot,
    restore_snapshot,
)
from shared_memory.database import init_db


@pytest.mark.asyncio
async def test_save_and_read_memory_flow(mock_gemini):
    # Setup
    init_db()
    # The compute_embedding function in server.py uses response.embedding
    mock_gemini.embed_content.return_value = MagicMock(embedding=[0.1] * 768)

    # 1. Save Memory
    await save_memory(
        entities=[
            {
                "name": "Python",
                "entity_type": "Language",
                "description": "Programming language",
            }
        ],
        agent_id="test_agent",
    )

    # 2. Read Memory
    response = await read_memory(query="Python")
    assert "graph" in response
    assert len(response["graph"]["entities"]) == 1
    assert response["graph"]["entities"][0]["name"] == "Python"

    # 3. Check Audit Log
    history = get_audit_history("Python")
    assert len(history) > 0
    assert history[0]["agent"] == "test_agent"
    assert history[0]["action"] == "INSERT"


@pytest.mark.asyncio
async def test_snapshot_restore(mock_gemini, temp_db):
    init_db()
    await save_memory(entities=[{"name": "PreSnapshot", "entity_type": "Test"}])

    # Create Snapshot
    await create_snapshot("Milestone 1")

    # Delete data
    delete_memory(["PreSnapshot"])
    res = await read_memory(query="PreSnapshot")
    assert len(res["graph"]["entities"]) == 0

    # Restore Snapshot
    await restore_snapshot(1)
    res_restored = await read_memory(query="PreSnapshot")
    assert len(res_restored["graph"]["entities"]) == 1
    assert res_restored["graph"]["entities"][0]["name"] == "PreSnapshot"


@pytest.mark.asyncio
async def test_memory_health_gaps(mock_gemini):
    init_db()
    # Save an isolated entity
    await save_memory(entities=[{"name": "Isolated", "entity_type": "Island"}])

    health = await get_memory_health()
    assert health["entities_count"] == 1
    assert health["gaps_analysis"]["isolated_entities_count"] == 1
