import pytest
from shared_memory.core import logic
from tests.unit.fake_client import FakeGeminiClient
from unittest.mock import patch

@pytest.fixture
def fake_client():
    return FakeGeminiClient()

@pytest.mark.asyncio
async def test_normalize_entities():
    # Test strings
    input_entities = ["Python", {"name": "FastMCP", "type": "Library"}]
    normalized = logic.normalize_entities(input_entities)
    
    assert len(normalized) == 2
    assert normalized[0]["name"] == "Python"
    assert normalized[0]["entity_type"] == "concept"
    assert normalized[1]["name"] == "FastMCP"
    assert normalized[1]["entity_type"] == "Library"

@pytest.mark.asyncio
async def test_normalize_observations():
    input_obs = ["It works", {"observation": "Real fact", "entity": "Test"}]
    normalized = logic.normalize_observations(input_obs)
    
    assert len(normalized) == 2
    assert normalized[0]["content"] == "It works"
    assert normalized[0]["entity_name"] == "Global"
    assert normalized[1]["content"] == "Real fact"
    assert normalized[1]["entity_name"] == "Test"

@pytest.mark.asyncio
async def test_normalize_bank_files():
    # Various formats
    input_files = {
        "readme.md": "Hello",
        "data.json": '{"a": 1}'
    }
    normalized = logic.normalize_bank_files(input_files)
    assert normalized["readme.md"] == "Hello"
    
    input_list = [{"filename": "list.md", "content": "list content"}]
    normalized_list = logic.normalize_bank_files(input_list)
    assert normalized_list["list.md"] == "list content"

@pytest.mark.asyncio
async def test_save_memory_core_basic(fake_client):
    # Use patch to inject fake client WITHOUT MagicMock for the logic being tested
    # Although we use patch, the object returned is FakeGeminiClient which is real code.
    with patch("shared_memory.infra.embeddings.get_gemini_client", return_value=fake_client):
        with patch("shared_memory.core.graph.get_gemini_client", return_value=fake_client):
            result = await logic.save_memory_core(
                entities=["UnitEntity"],
                observations=[{"content": "Unit content", "entity_name": "UnitEntity"}]
            )
            assert "Saved 1 entities" in result
            assert "Saved 1 observations" in result

@pytest.mark.asyncio
async def test_save_memory_core_ai_error(fake_client):
    # Simulate AI failure
    fake_client.models.set_error("embed_content", Exception("AI Down"))
    
    with patch("shared_memory.infra.embeddings.get_gemini_client", return_value=fake_client):
        result = await logic.save_memory_core(entities=["ErrorEntity"])
        assert "AI Error" in result
