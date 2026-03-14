from fastmcp import FastMCP
import sqlite3
import os
import aiofiles
import json
from typing import List, Optional, Dict, Any

mcp = FastMCP("SharedMemoryServer")

# --- CONFIGURATION HELPERS ---
def get_db_path():
    return os.environ.get("MEMORY_DB_PATH", "shared_memory.db")

def get_bank_dir():
    return os.environ.get("MEMORY_BANK_DIR", "memory-bank")

# --- KNOWLEDGE GRAPH STORAGE (SQLite) ---
def init_db():
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            name TEXT PRIMARY KEY,
            entity_type TEXT,
            description TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relations (
            source TEXT,
            target TEXT,
            relation_type TEXT,
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
            FOREIGN KEY (entity_name) REFERENCES entities (name) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

# --- MEMORY BANK STORAGE (Markdown) ---
BANK_FILES = {
    "projectBrief.md": "Core requirements and goals.",
    "productContext.md": "Why this project exists and its scope.",
    "activeContext.md": "What we are working on now and recent decisions.",
    "systemPatterns.md": "Architecture, design patterns, and technical decisions.",
    "techContext.md": "Tech stack, dependencies, and constraints.",
    "progress.md": "Status, roadmap, and what's next.",
    "decisionLog.md": "Record of significant technical choices."
}

async def initialize_bank():
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir)
    for filename, description in BANK_FILES.items():
        path = os.path.join(bank_dir, filename)
        if not os.path.exists(path):
            async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
                await f.write(f"# {filename}\n\n{description}\n\n## Status\n- Initialized\n")

# --- GRAPH TOOLS (Official MCP Logic) ---

@mcp.tool()
def create_entities(entities: List[Dict[str, str]]):
    """Creates multiple entities in the knowledge graph. Each dict should have 'name', 'entity_type', 'description'."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for e in entities:
            conn.execute("INSERT OR REPLACE INTO entities (name, entity_type, description) VALUES (?, ?, ?)", 
                         (e['name'], e['entity_type'], e.get('description', '')))
        conn.commit()
        return f"Successfully created {len(entities)} entities."
    finally:
        conn.close()

@mcp.tool()
def create_relations(relations: List[Dict[str, str]]):
    """Creates directed relations between entities. Each dict should have 'source', 'target', 'relation_type'."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for r in relations:
            conn.execute("INSERT OR REPLACE INTO relations (source, target, relation_type) VALUES (?, ?, ?)", 
                         (r['source'], r['target'], r['relation_type']))
        conn.commit()
        return f"Successfully created {len(relations)} relations."
    finally:
        conn.close()

@mcp.tool()
def add_observations(observations: List[Dict[str, str]]):
    """Adds factual observations to entities. Each dict should have 'entity_name', 'content'."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for o in observations:
            conn.execute("INSERT INTO observations (entity_name, content) VALUES (?, ?)", 
                         (o['entity_name'], o['content']))
        conn.commit()
        return f"Successfully added {len(observations)} observations."
    finally:
        conn.close()

@mcp.tool()
def read_graph():
    """Returns the entire knowledge graph (entities, relations, observations)."""
    conn = sqlite3.connect(get_db_path())
    try:
        cursor = conn.cursor()
        entities = cursor.execute("SELECT * FROM entities").fetchall()
        relations = cursor.execute("SELECT * FROM relations").fetchall()
        obs = cursor.execute("SELECT * FROM observations").fetchall()
        
        return {
            "entities": [{"name": e[0], "type": e[1], "description": e[2]} for e in entities],
            "relations": [{"source": r[0], "target": r[1], "type": r[2]} for r in relations],
            "observations": [{"entity": o[1], "content": o[2], "at": o[3]} for o in obs]
        }
    finally:
        conn.close()

@mcp.tool()
def delete_entities(entity_names: List[str]):
    """Removes entities and their associated relations/observations."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for name in entity_names:
            conn.execute("DELETE FROM entities WHERE name = ?", (name,))
        conn.commit()
        return f"Deleted {len(entity_names)} entities."
    finally:
        conn.close()

@mcp.tool()
def search_nodes(query: str):
    """Searches for entities or observations containing the query string."""
    conn = sqlite3.connect(get_db_path())
    try:
        cursor = conn.cursor()
        q = f"%{query}%"
        e_matches = cursor.execute("SELECT * FROM entities WHERE name LIKE ? OR description LIKE ?", (q, q)).fetchall()
        o_matches = cursor.execute("SELECT * FROM observations WHERE content LIKE ?", (q,)).fetchall()
        
        return {
            "query": query,
            "entity_matches": [{"name": e[0], "type": e[1], "description": e[2]} for e in e_matches],
            "observation_matches": [{"entity": o[1], "content": o[2], "at": o[3]} for o in o_matches]
        }
    finally:
        conn.close()

# --- MEMORY BANK TOOLS (Cline/Roo Logic) ---

@mcp.tool()
async def read_memory_bank():
    """Reads all active files in the memory-bank directory for full context."""
    bank_dir = get_bank_dir()
    bank_data = {}
    if not os.path.exists(bank_dir):
        return "ERROR: Memory bank not initialized."
    
    for filename in os.listdir(bank_dir):
        if filename.endswith(".md"):
            path = os.path.join(bank_dir, filename)
            async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
                bank_data[filename] = await f.read()
    return bank_data

@mcp.tool()
async def update_bank_file(filename: str, content: str):
    """Updates or creates a specific markdown file in the memory bank."""
    bank_dir = get_bank_dir()
    if not filename.endswith(".md"):
        filename += ".md"
    path = os.path.join(bank_dir, filename)
    async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
        await f.write(content)
    return f"Updated {filename}."

# --- INITIALIZATION ---
def main():
    init_db()
    import asyncio
    asyncio.run(initialize_bank())
    mcp.run()

if __name__ == "__main__":
    main()
