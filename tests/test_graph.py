import pytest

from shared_memory.database import get_connection, init_db, update_access
from shared_memory.graph import save_entities, save_observations, save_relations


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


@pytest.mark.asyncio
async def test_save_entities(mock_gemini):
    conn = get_connection()
    entities = [
        {"name": "Alice", "entity_type": "person", "description": "A developer"},
        {"name": "Bob", "entity_type": "person", "description": "A designer"},
    ]
    res = await save_entities(entities, "test_agent", conn)
    conn.commit()

    assert "Saved 2 entities" in res

    # Verify in DB
    row = conn.execute(
        "SELECT name, entity_type FROM entities WHERE name = 'Alice'"
    ).fetchone()
    assert row[0] == "Alice"
    assert row[1] == "person"
    conn.close()


@pytest.mark.asyncio
async def test_access_stability():
    conn = get_connection()
    try:
        # Insert a dummy knowledge metadata entry for testing
        conn.execute(
            "INSERT INTO knowledge_metadata (content_id, access_count, stability) VALUES ('test_node', 0, 0.5)"
        )
        conn.commit()

        # First access
        await update_access("test_node", conn)

        row = conn.execute(
            "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = 'test_node'"
        ).fetchone()
        assert row[0] == 1
        initial_stability = row[1]

        # Second access (stability should increase)
        await update_access("test_node", conn)
        row = conn.execute(
            "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = 'test_node'"
        ).fetchone()
        assert row[0] == 2
        assert row[1] > initial_stability
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_save_relations():
    conn = get_connection()
    try:
        # Need entities first
        conn.execute("INSERT INTO entities (name) VALUES ('Alice'), ('Bob')")

        relations = [{"source": "Alice", "target": "Bob", "relation_type": "colleague"}]
        res = await save_relations(relations, "test_agent", conn)
        conn.commit()

        assert "Saved 1 relations" in res
        row = conn.execute(
            "SELECT relation_type FROM relations WHERE source = 'Alice'"
        ).fetchone()
        assert row[0] == "colleague"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_save_observations(mock_gemini):
    conn = get_connection()
    conn.execute("INSERT INTO entities (name) VALUES ('Alice')")

    obs = [{"entity_name": "Alice", "content": "Likes Python"}]
    res, conflicts = await save_observations(obs, "test_agent", conn)
    conn.commit()

    assert "Saved 1 observations" in res
    assert len(conflicts) == 0

    row = conn.execute(
        "SELECT content FROM observations WHERE entity_name = 'Alice'"
    ).fetchone()
    assert row[0] == "Likes Python"
    conn.close()


@pytest.mark.asyncio
async def test_conflict_detection(mock_gemini):
    # Setup: Mock Gemini to return a conflict
    mock_gemini.models.generate_content.return_value.text = (
        '{"conflict": true, "reason": "Contradicts previous info"}'
    )

    conn = get_connection()
    conn.execute("INSERT INTO entities (name) VALUES ('Alice')")
    conn.execute(
        "INSERT INTO observations (entity_name, content) VALUES ('Alice', 'Alice is in Tokyo')"
    )

    obs = [{"entity_name": "Alice", "content": "Alice is in London"}]
    res, conflicts = await save_observations(obs, "test_agent", conn)

    assert len(conflicts) == 1
    assert conflicts[0]["entity"] == "Alice"
    assert "Contradicts" in conflicts[0]["reason"]
    conn.close()


@pytest.mark.asyncio
async def test_get_graph_data():
    init_db()
    conn = get_connection()
    conn.execute("INSERT INTO entities (name, entity_type) VALUES ('Alice', 'person')")
    conn.execute("INSERT INTO entities (name, entity_type) VALUES ('Bob', 'person')")
    conn.execute(
        "INSERT INTO relations (source, target, relation_type) VALUES ('Alice', 'Bob', 'knows')"
    )
    conn.execute(
        "INSERT INTO observations (entity_name, content) VALUES ('Alice', 'Works hard')"
    )
    conn.commit()
    conn.close()


@pytest.mark.asyncio
async def test_save_entities_invalid_input(mock_gemini):
    conn = get_connection()
    # 1. Empty name
    res = await save_entities(
        [{"name": "", "description": "no name"}], "test_agent", conn
    )
    assert "Error" in res

    # 2. Out of range importance (should be clamped/defaulted)
    await save_entities([{"name": "ClampMe", "importance": 100}], "test_agent", conn)
    row = conn.execute(
        "SELECT importance FROM entities WHERE name = 'ClampMe'"
    ).fetchone()
    assert row[0] == 10

    conn.close()


@pytest.mark.asyncio
async def test_save_relations_invalid_input():
    conn = get_connection()
    # Missing fields
    res = await save_relations([{"source": "A"}], "test_agent", conn)
    assert "Errors: 1" in res
    conn.close()


@pytest.mark.asyncio
async def test_save_observations_side_effects(mock_gemini):
    conn = get_connection()
    conn.execute("INSERT INTO entities (name, importance) VALUES ('Alice', 5)")
    conn.commit()

    # Saving an observation should increment importance
    await save_observations(
        [{"entity_name": "Alice", "content": "Update"}], "test_agent", conn
    )
    conn.commit()

    row = conn.execute(
        "SELECT importance FROM entities WHERE name = 'Alice'"
    ).fetchone()
    assert row[0] == 6
    conn.close()
