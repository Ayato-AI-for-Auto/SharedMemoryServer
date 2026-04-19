import asyncio
from unittest.mock import AsyncMock

import aiosqlite
import pytest

from shared_memory.database import DatabaseLockedError, retry_on_db_lock


@pytest.mark.asyncio
async def test_retry_on_db_lock_success_unit():
    """Unit test: Verify that the retry decorator eventually succeeds."""
    mock_func = AsyncMock()
    # Fail twice with lock, then succeed
    mock_func.side_effect = [
        aiosqlite.OperationalError("database is locked"),
        aiosqlite.OperationalError("database is locked"),
        "success",
    ]

    # Patch sleep to speed up test
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(asyncio, "sleep", AsyncMock())

        decorated = retry_on_db_lock(max_retries=5, initial_delay=0.01)(mock_func)
        result = await decorated()

        assert result == "success"
        assert mock_func.call_count == 3


@pytest.mark.asyncio
async def test_retry_on_db_lock_exhausted_unit():
    """Unit test: Verify that the retry decorator raises after max_retries."""
    mock_func = AsyncMock()
    mock_func.side_effect = aiosqlite.OperationalError("database is locked")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(asyncio, "sleep", AsyncMock())

        decorated = retry_on_db_lock(max_retries=3, initial_delay=0.01)(mock_func)

        with pytest.raises(DatabaseLockedError):
            await decorated()

        assert mock_func.call_count == 3


@pytest.mark.asyncio
async def test_retry_on_db_lock_other_error_unit():
    """Unit test: Verify that non-lock OperationalErrors are raised immediately."""
    mock_func = AsyncMock()
    mock_func.side_effect = aiosqlite.OperationalError("Some other error")
    decorated = retry_on_db_lock(max_retries=5)(mock_func)

    with pytest.raises(aiosqlite.OperationalError):
        await decorated()

    assert mock_func.call_count == 1
