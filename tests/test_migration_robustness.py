import sqlite3
import os
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from shared_memory.database import _add_column_if_missing, init_db, retry_on_db_lock
from shared_memory.server import save_memory

@pytest.fixture
def mock_db_path(tmp_path):
    """Fixture to provide a clean temporary DB path for each test."""
    db_path = tmp_path / "test_memory.db"
    with patch("shared_memory.database.get_db_path", return_value=str(db_path)):
        with patch("shared_memory.utils.get_db_path", return_value=str(db_path)):
            yield str(db_path)

def test_add_column_if_missing_success():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE test (id INTEGER)")
    _add_column_if_missing(cursor, "test", "name TEXT")
    cursor.execute("PRAGMA table_info(test)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "name" in columns

def test_add_column_if_missing_already_exists():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE test (id INTEGER, name TEXT)")
    _add_column_if_missing(cursor, "test", "name TEXT")
    cursor.execute("PRAGMA table_info(test)")
    columns = [row[1] for row in cursor.fetchall()]
    assert columns.count("name") == 1

def test_add_column_if_missing_raises_on_invalid_sql():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE test (id INTEGER)")
    with pytest.raises(sqlite3.OperationalError):
        _add_column_if_missing(cursor, "test", "INVALID COLUMN TYPE !!!")

def test_retry_on_db_lock_logic():
    mock_func = MagicMock()
    mock_func.side_effect = sqlite3.OperationalError("database is locked")
    decorated_func = retry_on_db_lock(max_retries=3, initial_delay=0.01)(mock_func)
    with pytest.raises(sqlite3.OperationalError):
        decorated_func()
    assert mock_func.call_count == 3

def test_zero_suppression_policy_check():
    import shared_memory
    src_dir = os.path.dirname(os.path.abspath(shared_memory.__file__))
    import re
    suppression_pattern = r"except.*:[\s]*pass"
    violations = []
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if re.search(suppression_pattern, content):
                        violations.append(path)
    assert not violations, f"Zero-Suppression Policy Violation in: {violations}"

@pytest.mark.asyncio
async def test_save_memory_validation(mock_db_path):
    """Verify data validation in save_memory."""
    # 1. Empty name
    with pytest.raises(ValueError, match="Entity 'name' is required"):
        await save_memory(entities=[{"name": "", "description": "test"}])
    
    # 2. Out of range importance
    with pytest.raises(ValueError, match="Importance .* must be between 1 and 10"):
        await save_memory(entities=[{"name": "test", "importance": 11}])
        
    # 3. Missing fields in relations
    with pytest.raises(ValueError, match="Relation requires 'source'"):
        await save_memory(relations=[{"source": "A", "target": "B"}])

def test_init_db_idempotency(mock_db_path):
    # First run
    init_db()
    assert os.path.exists(mock_db_path)
    
    # Verify schema
    conn = sqlite3.connect(mock_db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(entities)")
    cols = [r[1] for r in cursor.fetchall()]
    assert "importance" in cols
    conn.close()
    
    # Second run
    init_db()
