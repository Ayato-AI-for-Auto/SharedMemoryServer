import sqlite3
import pytest
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


@pytest.mark.asyncio
async def test_update_access_and_stability(temp_db):
    init_db()
    # Insert a mock entity first (FK constraint)
    conn = get_connection()
    conn.execute(
        "INSERT INTO entities (name, entity_type) VALUES ('test_node', 'test')"
    )
    conn.commit()

    try:
        # First access
        await update_access("test_node")

        row = conn.execute(
            "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = 'test_node'"
        ).fetchone()
        assert row[0] == 1
        initial_stability = row[1]

        # Second access (stability should increase)
        await update_access("test_node")
        row = conn.execute(
            "SELECT access_count, stability FROM knowledge_metadata WHERE content_id = 'test_node'"
        ).fetchone()
        assert row[0] == 2
        assert row[1] > initial_stability
    finally:
        conn.close()


def test_migration_from_partial_schema(temp_db):
    """Verifies that init_db correctly migrates a database with a partial schema."""
    # 1. Setup a partial schema (simulating an older version)
    conn = sqlite3.connect(temp_db)
    conn.execute(
        """
        CREATE TABLE entities (
            name TEXT PRIMARY KEY,
            entity_type TEXT,
            description TEXT
        )
    """
    )
    # Add only one of the migration columns to trigger the original bug
    conn.execute(
        "ALTER TABLE entities ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    )
    conn.commit()
    conn.close()

    # 2. Run init_db()
    init_db()

    # 3. Verify all columns are now present
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(entities)")
    columns = [col[1] for col in cursor.fetchall()]
    conn.close()

    expected_columns = [
        "name",
        "entity_type",
        "description",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "importance",
    ]
    for col in expected_columns:
        assert col in columns, f"Column {col} is missing from entities table"


def test_migration_relations_partial(temp_db):
    """Verifies that relations table is correctly migrated if columns are missing."""
    # Setup partial relations table
    conn = sqlite3.connect(temp_db)
    conn.execute("CREATE TABLE entities (name TEXT PRIMARY KEY)")
    conn.execute(
        """
        CREATE TABLE relations (
            source TEXT,
            target TEXT,
            relation_type TEXT,
            PRIMARY KEY (source, target, relation_type),
            FOREIGN KEY (source) REFERENCES entities (name),
            FOREIGN KEY (target) REFERENCES entities (name)
        )
    """
    )
    conn.execute(
        "ALTER TABLE relations ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    )
    conn.commit()
    conn.close()

    init_db()

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(relations)")
    columns = [col[1] for col in cursor.fetchall()]
    conn.close()

    assert "created_by" in columns
