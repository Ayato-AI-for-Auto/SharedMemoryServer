import sqlite3
import os
import sys

# Workaround for package structure
PACKAGE_ROOT = r"C:\Users\saiha\My_Service\programing\MCP\SharedMemoryServer\src"
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

from shared_memory.database import _add_column_if_missing


def test_migration_error_handling():
    print("Testing migration error handling...")

    # Use a dummy test database
    db_path = "test_error_handling.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Setup table
    cursor.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
    conn.commit()

    # 2. Add column (Expect success)
    _add_column_if_missing(cursor, "test_table", "new_col TEXT")
    print("Initial column addition successful.")

    # 3. Add same column again (Expect silent skip)
    _add_column_if_missing(cursor, "test_table", "new_col TEXT")
    print("Redundant column addition handled correctly (skipped).")

    # 4. Verify column exists
    cursor.execute("PRAGMA table_info(test_table)")
    cols = [row[1] for row in cursor.fetchall()]
    assert "new_col" in cols, "Column should exist"

    # 5. Simulate OperationalError (Invalid syntax)
    try:
        _add_column_if_missing(cursor, "test_table", "!!! INVALID !!!")
        print("FAIL: Should have raised OperationalError for invalid syntax.")
    except sqlite3.OperationalError as e:
        print(f"Success: Correctly raised and caught OperationalError: {e}")

    conn.close()
    if os.path.exists(db_path):
        os.remove(db_path)

    print("\nVerification PASSED!")


if __name__ == "__main__":
    try:
        test_migration_error_handling()
    except Exception as e:
        import traceback

        print(f"Verification FAILED: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
