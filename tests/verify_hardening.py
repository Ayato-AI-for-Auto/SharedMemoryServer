import sqlite3
import os
import sys
import asyncio
from unittest.mock import MagicMock, patch

# Ensure we can import the shared_memory package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from shared_memory.database import _add_column_if_missing, init_db, retry_on_db_lock
from shared_memory.server import save_memory

def test_add_column_if_missing_success():
    print("Testing _add_column_if_missing success...")
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE test (id INTEGER)")
    _add_column_if_missing(cursor, "test", "name TEXT")
    cursor.execute("PRAGMA table_info(test)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "name" in columns
    print("  OK")

def test_add_column_if_missing_already_exists():
    print("Testing _add_column_if_missing idempotency...")
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE test (id INTEGER, name TEXT)")
    _add_column_if_missing(cursor, "test", "name TEXT")
    cursor.execute("PRAGMA table_info(test)")
    columns = [row[1] for row in cursor.fetchall()]
    assert columns.count("name") == 1
    print("  OK")

def test_add_column_if_missing_raises_on_invalid_sql():
    print("Testing _add_column_if_missing re-raising...")
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE test (id INTEGER)")
    try:
        _add_column_if_missing(cursor, "test", "INVALID COLUMN TYPE !!!")
        assert False, "Should have raised OperationalError"
    except sqlite3.OperationalError:
        print("  OK (Raised as expected)")

def test_retry_on_db_lock_logic():
    print("Testing retry_on_db_lock...")
    mock_func = MagicMock()
    mock_func.side_effect = sqlite3.OperationalError("database is locked")
    decorated_func = retry_on_db_lock(max_retries=3, initial_delay=0.01)(mock_func)
    try:
        decorated_func()
        assert False, "Should have raised OperationalError"
    except sqlite3.OperationalError:
        assert mock_func.call_count == 3
        print("  OK (Retried 3 times and raised)")

def test_zero_suppression_policy_check():
    print("Testing Zero-Suppression Policy integrity...")
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
    if violations:
        print(f"  FAILED: Violations in {violations}")
        exit(1)
    else:
        print("  OK (No 'except ...: pass' found)")

async def test_save_memory_validation(tmp_path):
    print("Testing save_memory data validation...")
    db_path = os.path.join(tmp_path, "test_validation.db")
    with patch("shared_memory.database.get_db_path", return_value=db_path):
        with patch("shared_memory.utils.get_db_path", return_value=db_path):
            # 1. Empty name
            res = await save_memory(entities=[{"name": "", "description": "test"}])
            print(f"  DEBUG: res={res}")
            assert res["status"] == "error"
            assert "name" in res["message"].lower() and "required" in res["message"].lower()
            
            # 2. Out of range importance
            res = await save_memory(entities=[{"name": "test", "importance": 11}])
            print(f"  DEBUG: res={res}")
            assert res["status"] == "error"
            assert "importance" in res["message"].lower()
                
            # 3. Missing fields in relations
            res = await save_memory(relations=[{"source": "A", "target": "B"}])
            print(f"  DEBUG: res={res}")
            assert res["status"] == "error"
            assert "relation requires" in res["message"].lower()
    print("  OK")

async def main():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_add_column_if_missing_success()
        test_add_column_if_missing_already_exists()
        test_add_column_if_missing_raises_on_invalid_sql()
        test_retry_on_db_lock_logic()
        test_zero_suppression_policy_check()
        await test_save_memory_validation(tmp_dir)
        print("\n🎉 ALL HARDENING TESTS PASSED! 🎉")

if __name__ == "__main__":
    asyncio.run(main())
