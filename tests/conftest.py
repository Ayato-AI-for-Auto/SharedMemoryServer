import os
import pytest
import sqlite3
import shutil
import tempfile
from unittest.mock import MagicMock, patch

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
    with patch.dict(os.environ, {
        "MEMORY_DB_PATH": temp_db,
        "MEMORY_BANK_DIR": temp_bank,
        "GOOGLE_API_KEY": "mock_key"
    }):
        yield

@pytest.fixture
def mock_gemini():
    """Mocks the Gemini embedding client."""
    with patch("shared_memory.embeddings.get_gemini_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client
