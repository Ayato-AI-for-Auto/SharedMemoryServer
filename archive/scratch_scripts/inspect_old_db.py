import sqlite3
import os

db_path = "shared_memory.db"
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM entities")
        count = cursor.fetchone()[0]
        print(f"Entities in {db_path}: {count}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"{db_path} not found")
