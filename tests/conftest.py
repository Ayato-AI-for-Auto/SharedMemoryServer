import os
import pytest
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
    with patch.dict(
        os.environ,
        {
            "MEMORY_DB_PATH": temp_db,
            "MEMORY_BANK_DIR": temp_bank,
            "GOOGLE_API_KEY": "mock_key",
        },
    ):
        yield


@pytest.fixture
def mock_gemini():
    """Mocks the Gemini client for embeddings and generation."""
    # We must patch where it's USED because of "from ... import ..."
    with (
        patch("shared_memory.embeddings.get_gemini_client") as mock_get_eb,
        patch("shared_memory.server.get_gemini_client") as mock_get_sv,
    ):
        mock_client = MagicMock()
        mock_get_eb.return_value = mock_client
        mock_get_sv.return_value = mock_client

        # Mock for embeddings: client.models.embed_content(...).embeddings[0].values
        mock_embedding_result = MagicMock()
        mock_embedding_result.embeddings = [MagicMock(values=[0.1] * 768)]
        mock_client.models.embed_content.return_value = mock_embedding_result

        # Mock for generation: client.models.generate_content(...).text
        mock_client.models.generate_content.return_value = MagicMock(
            text='{"conflict": false, "reason": ""}'
        )

        yield mock_client
