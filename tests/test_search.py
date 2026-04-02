import json

import pytest

from shared_memory.database import get_connection, init_db
from shared_memory.logic import (
    read_memory_core as perform_search,
)
from shared_memory.logic import (
    synthesize_entity as synthesize_knowledge,
)


@pytest.fixture(autouse=True)
def setup_db(mock_gemini):
    init_db()


@pytest.mark.asyncio
async def test_perform_search(mock_gemini):
    conn = get_connection()
    # Mock data
    conn.execute(
        "INSERT INTO entities (name, description) VALUES ('Python', 'A programming language')"
    )
    conn.execute(
        "INSERT INTO bank_files (filename, content) VALUES ('python_guide.md', 'Python is great')"
    )
    # Mock embedding and metadata
    vector_json = json.dumps([0.1] * 768).encode("utf-8")
    conn.execute(
        "INSERT INTO embeddings (content_id, vector, model_name) VALUES ('Python', ?, 'models/text-embedding-004')",
        (vector_json,),
    )
    conn.execute(
        "INSERT INTO knowledge_metadata (content_id, access_count) VALUES ('Python', 10)"
    )
    conn.commit()
    conn.close()

    # Run search
    res = await perform_search("Python")
    graph_data = res["graph"]

    assert any(e["name"] == "Python" for e in graph_data["entities"])
    # If search found nothing, it fallbacks to keyword
    # But since we mocked Gemini to return [0.1]*768, it should find something


@pytest.mark.asyncio
async def test_synthesize_knowledge(mock_gemini):
    conn = get_connection()
    conn.execute(
        "INSERT INTO entities (name, entity_type, description) VALUES ('Alice', 'person', 'Dev')"
    )
    conn.execute(
        "INSERT INTO entities (name, entity_type, description) VALUES ('Project X', 'concept', 'A project')"
    )
    conn.execute(
        "INSERT INTO observations (entity_name, content) VALUES ('Alice', 'Expert in Go')"
    )
    conn.execute(
        "INSERT INTO relations (source, target, relation_type) VALUES ('Alice', 'Project X', 'leads')"
    )
    conn.commit()
    conn.close()

    # Mock generation
    mock_gemini.models.generate_content.return_value.text = (
        "Alice is a leading Go developer on Project X."
    )

    res = await synthesize_knowledge("Alice")
    assert "Alice" in res
    assert "Go" in res
