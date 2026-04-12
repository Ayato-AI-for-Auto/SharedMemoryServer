import os
import tempfile
from unittest.mock import patch

import aiosqlite
import pytest


@pytest.mark.asyncio
async def test_robust_initialization_from_scratch(request):
    """
    [System Test]
    Verifies that calling sequential_thinking from a completely fresh env
    correctly initializes all tables without throwing 'no such table' errors.
    """
    from shared_memory import database, thought_logic
    from shared_memory.thought_logic import process_thought_core
    from shared_memory.utils import get_db_path, get_thoughts_db_path

    # 1. Reset global flags for this specific test
    # (Since other tests might have already initialized the DB in this process)
    database._DB_INITIALIZED = False
    thought_logic._THOUGHTS_INITIALIZED = False

    # 2. Setup a fresh isolated environment using tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Use patch.dict to ensure we override conftest.py's autouse fixture
        new_env = {
            "SHARED_MEMORY_HOME": tmp_dir,
            "MEMORY_DB_PATH": os.path.join(tmp_dir, "knowledge.db"),
            "THOUGHTS_DB_PATH": os.path.join(tmp_dir, "thoughts.db"),
            "MEMORY_BANK_DIR": os.path.join(tmp_dir, "bank"),
        }

        with patch.dict(os.environ, new_env):
            db_path = get_db_path()
            t_db_path = get_thoughts_db_path()

            # Ensure we are actually in the temp dir
            assert tmp_dir in db_path
            if os.path.exists(db_path):
                os.remove(db_path)
            if os.path.exists(t_db_path):
                os.remove(t_db_path)

            # 3. Trigger the tool (sequential_thinking -> process_thought_core)
            # This will internally call log_search_stat which uses search_stats table.
            result = await process_thought_core(
                thought="Testing lazy initialization",
                thought_number=1,
                total_thoughts=1,
                next_thought_needed=False,
                session_id="test_init_session",
            )

            # 4. Assertions
            assert "thoughtNumber" in result
            assert os.path.exists(db_path)
            assert os.path.exists(t_db_path)

            # 5. Deep Inspection: Verify search_stats table exists
            async with aiosqlite.connect(db_path) as conn:
                q = (
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='search_stats'"
                )
                cursor = await conn.execute(q)
                assert await cursor.fetchone() is not None
