import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
async def setup_teardown_db(request):
    from shared_memory.database import close_all_connections, init_db
    from shared_memory.thought_logic import init_thoughts_db

    # Standard path resolution for testing
    home_dir = tempfile.mkdtemp()
    os.environ["SHARED_MEMORY_HOME"] = home_dir
    os.environ["MEMORY_DB_PATH"] = os.path.join(home_dir, "knowledge.db")
    os.environ["THOUGHTS_DB_PATH"] = os.path.join(home_dir, "thoughts.db")
    os.environ["MEMORY_BANK_DIR"] = os.path.join(home_dir, "bank")

    # Initialize databases for each test
    await init_db(force=True)
    await init_thoughts_db(force=True)

    yield

    # Teardown: Close singleton connections before rmtree (Windows requirement)
    await close_all_connections()
    if os.path.exists(home_dir):
        shutil.rmtree(home_dir, ignore_errors=True)


@pytest.fixture
def mock_gemini_client():
    """
    Returns a controlled FakeGeminiClient that supports both sync
    and the new `aio` async interface.
    """
    from tests.unit.fake_client import FakeGeminiClient
    client = FakeGeminiClient()
    with patch("shared_memory.embeddings.get_gemini_client", return_value=client), \
         patch("shared_memory.distiller.get_gemini_client", return_value=client):
        yield client


@pytest.fixture(autouse=True)
def mock_llm():
    """
    Universal LLM mock that ensures no real network calls occur during tests.
    Supports FastMCP tool testing and direct logic calls.
    """
    from unittest.mock import AsyncMock

    mock_client = MagicMock()

    # Sync Models
    def mock_embed_content(model, contents, config=None):
        mock_response = MagicMock()
        from unittest.mock import MagicMock as MockVal
        val = MockVal()
        val.values = [0.1] * 768
        mock_response.embeddings = [val] * len(contents)
        return mock_response

    mock_client.models.embed_content.side_effect = mock_embed_content
    mock_client.models.generate_content.return_value.text = json.dumps({
        "conflict": False, "reason": "Consistent"
    })

    # Async Models (aio)
    mock_aio_models = AsyncMock()
    mock_aio_models.embed_content.side_effect = mock_embed_content
    mock_aio_models.generate_content.return_value.text = json.dumps({
        "conflict": False, "reason": "Consistent"
    })

    # Model listing (async)
    mock_model = MagicMock()
    mock_model.name = "models/text-embedding-004"
    mock_aio_models.list.return_value = [mock_model]

    mock_client.aio = MagicMock()
    mock_client.aio.models = mock_aio_models

    patches = [
        patch("shared_memory.embeddings.get_gemini_client"),
        patch("shared_memory.distiller.get_gemini_client")
    ]

    handlers = []
    for p in patches:
        h = p.start()
        h.return_value = mock_client
        handlers.append(p)

    try:
        yield mock_client
    finally:
        for p in handlers:
            p.stop()


@pytest.fixture(autouse=True)
def mock_gemini_globally(mock_llm):
    """Alias for mock_llm for tests that expect this name."""
    return mock_llm


@contextmanager
def temp_env(env_vars):
    """Temporary environment variable manager."""
    old_env = os.environ.copy()
    os.environ.update(env_vars)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)
