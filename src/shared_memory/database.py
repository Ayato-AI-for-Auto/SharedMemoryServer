import sqlite3
import time
import random

try:
    from .utils import get_db_path, log_error
except (ImportError, ValueError):
    from utils import get_db_path, log_error


def retry_on_db_lock(max_retries=5, initial_delay=0.1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e).lower():
                        retries += 1
                        if retries == max_retries:
                            raise
                        delay = initial_delay * (2 ** (retries - 1)) + random.uniform(
                            0, 0.1
                        )
                        time.sleep(delay)
                    else:
                        raise
            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _add_column_if_missing(cursor, table, col_def):
    """
    Safely adds a column to a table if it doesn't already exist.
    """
    col_name = col_def.split()[0]
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]

    if col_name in columns:
        return

    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
    except sqlite3.OperationalError as e:
        log_error(
            f"CRITICAL: Migration failed for table '{table}' adding '{col_def}'", e
        )
        raise


@retry_on_db_lock()
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            name TEXT PRIMARY KEY,
            entity_type TEXT,
            description TEXT,
            importance INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            updated_by TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relations (
            source TEXT,
            target TEXT,
            relation_type TEXT,
            justification TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            PRIMARY KEY (source, target, relation_type),
            FOREIGN KEY (source) REFERENCES entities (name) ON DELETE CASCADE,
            FOREIGN KEY (target) REFERENCES entities (name) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_name TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            FOREIGN KEY (entity_name) REFERENCES entities (name) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_files (
            filename TEXT PRIMARY KEY,
            content TEXT,
            last_synced DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            content_id TEXT PRIMARY KEY,
            vector BLOB,
            model_name TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_metadata (
            content_id TEXT PRIMARY KEY,
            access_count INTEGER DEFAULT 0,
            last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
            importance_score REAL DEFAULT 1.0,
            stability REAL DEFAULT 1.1,
            FOREIGN KEY (content_id) REFERENCES entities (name) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT,
            content_id TEXT,
            action TEXT,
            old_data TEXT,
            new_data TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            agent_id TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            db_path TEXT NOT NULL
        )
    """)
    # Conflicts table (New in Phase 13)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conflicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_name TEXT NOT NULL,
            existing_content TEXT NOT NULL,
            new_content TEXT NOT NULL,
            reason TEXT,
            agent_id TEXT,
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved INTEGER DEFAULT 0
        )
    """)
    # Migrations for Phase 11
    _add_column_if_missing(
        cursor, "entities", "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    )
    _add_column_if_missing(
        cursor, "entities", "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    )
    _add_column_if_missing(cursor, "entities", "created_by TEXT")
    _add_column_if_missing(cursor, "entities", "updated_by TEXT")
    _add_column_if_missing(cursor, "entities", "importance INTEGER DEFAULT 5")

    _add_column_if_missing(
        cursor, "relations", "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    )
    _add_column_if_missing(cursor, "relations", "created_by TEXT")

    _add_column_if_missing(cursor, "observations", "created_by TEXT")

    _add_column_if_missing(cursor, "bank_files", "updated_by TEXT")

    conn.commit()
    conn.close()


@retry_on_db_lock()
def update_access(content_id: str):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO knowledge_metadata (content_id, access_count, last_accessed, importance_score, stability)
            VALUES (?, 1, CURRENT_TIMESTAMP, 1.0, 1.1)
            ON CONFLICT(content_id) DO UPDATE SET
                access_count = access_count + 1,
                last_accessed = CURRENT_TIMESTAMP,
                stability = stability * 1.1
        """,
            (content_id,),
        )
        conn.commit()
    except Exception as e:
        log_error(f"Failed to update access for {content_id}", e)
    finally:
        conn.close()
