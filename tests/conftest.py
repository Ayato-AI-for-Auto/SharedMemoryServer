import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_db():
    """Provides a temporary database path and ensures it's cleaned up."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)
    # Also cleanup WAL files if any
    for ext in ["-wal", "-shm"]:
        if os.path.exists(path + ext):
            os.remove(path + ext)


@pytest.fixture
def temp_bank():
    """Provides a temporary memory bank directory."""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)


@pytest.fixture(autouse=True)
def mock_env(temp_db, temp_bank):
    """Mocks environment variables for testing."""
    env_vars = {
        "MEMORY_DB_PATH": temp_db,
        "MEMORY_BANK_DIR": temp_bank,
    }
    # Preserves actual API key if provided via environment or .env
    if "GOOGLE_API_KEY" not in os.environ:
        env_vars["GOOGLE_API_KEY"] = "mock_key"

    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture(autouse=True)
def mock_gemini():
    """
    Mocks the Gemini client by default.
    Patching at the source (embeddings.py) and entry points that still use direct imports.
    """
    patches = [
        patch("shared_memory.embeddings.get_gemini_client"),
        patch("shared_memory.search.get_gemini_client"),
        patch("shared_memory.management.get_gemini_client"),
        patch("shared_memory.distiller.get_gemini_client"),
    ]

    mock_client = MagicMock()

    # Default success behavior
    mock_embedding_result = MagicMock()
    mock_embedding_result.embeddings = [MagicMock(values=[0.1] * 768)]
    mock_client.models.embed_content.return_value = mock_embedding_result

    mock_client.models.generate_content.return_value = MagicMock(
        text='{"conflict": false, "reason": "No issues found.", "synthesis": "Project Omega is healthy.", "entities": [], "relations": [], "observations": []}'
    )

    # Models list mock
    mock_client.models.list.return_value = [
        type("Model", (), {"name": "models/gemini-pro"})
    ]

    handlers = []
    for p in patches:
        h = p.start()
        h.return_value = mock_client
        handlers.append(p)

    yield mock_client

    for p in handlers:
        p.stop()
