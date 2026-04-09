import pytest
from unittest.mock import patch
from shared_memory.embeddings import _get_text_hash, compute_embedding
from .fake_client import FakeGeminiClient

def test_get_text_hash_unit():
    """Unit test for hashing logic (deterministic)."""
    h1 = _get_text_hash("hello")
    h2 = _get_text_hash("hello")
    h3 = _get_text_hash("world")
    assert h1 == h2
    assert h1 != h3

@pytest.mark.asyncio
async def test_compute_embedding_caching_unit():
    """
    Unit test for compute_embedding caching logic.
    Uses FakeGeminiClient (NOT MagicMock).
    """
    fake_client = FakeGeminiClient()
    
    with patch("shared_memory.embeddings.get_gemini_client", return_value=fake_client):
        # 1. First call (should compute and save to cache)
        vec1 = await compute_embedding("cached_text")
        assert vec1 is not None
        assert len(vec1) == 768
        
        # 2. Second call (should hit cache)
        # We can verify this by checking that the cache entry exists in DB
        from shared_memory.database import async_get_connection
        async with await async_get_connection() as conn:
            text_hash = _get_text_hash("cached_text")
            cursor = await conn.execute(
                "SELECT vector FROM embedding_cache WHERE content_hash = ?",
                (text_hash,)
            )
            row = await cursor.fetchone()
            assert row is not None
