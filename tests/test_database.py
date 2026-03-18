import sqlite3
from shared_memory.database import init_db, get_connection, update_access


def test_init_db_creates_tables(temp_db):
    init_db()
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Check if a few key tables exist
    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [t[0] for t in tables]

    assert "entities" in table_names
    assert "knowledge_metadata" in table_names
    assert "audit_logs" in table_names
    assert "snapshots" in table_names
    conn.close()


def test_update_access_and_stability(temp_db):
    init_db()
    # Insert a mock entity first (FK constraint)
    conn = get_connection()
    conn.execute(
        "INSERT INTO entities (name, entity_type) VALUES ('test_node', 'test')"
    )
    conn.commit()

    # First access
    update_access("test_node")

    row = conn.execute(
        "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = 'test_node'"
    ).fetchone()
    assert row[0] == 1
    initial_stability = row[1]

    # Second access (stability should increase)
    update_access("test_node")
    row = conn.execute(
        "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = 'test_node'"
    ).fetchone()
    assert row[0] == 2
    assert row[1] > initial_stability
    conn.close()
