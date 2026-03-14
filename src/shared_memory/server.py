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

# --- UNIFIED TOOLS (V2 API) ---

@mcp.tool()
async def save_memory(
    entities: Optional[List[Dict[str, str]]] = None,
    relations: Optional[List[Dict[str, str]]] = None,
    observations: Optional[List[Dict[str, str]]] = None,
    bank_files: Optional[Dict[str, str]] = None
):
    """
    Unified write tool for both Knowledge Graph and Memory Bank.
    - entities: List of {name, entity_type, description}
    - relations: List of {source, target, relation_type}
    - observations: List of {entity_name, content}
    - bank_files: Dict of {filename: content}
    """
    results = []
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        if entities:
            for e in entities:
                conn.execute("INSERT OR REPLACE INTO entities (name, entity_type, description) VALUES (?, ?, ?)", 
                             (e['name'], e['entity_type'], e.get('description', '')))
            results.append(f"Saved {len(entities)} entities")
        
        if relations:
            for r in relations:
                conn.execute("INSERT OR REPLACE INTO relations (source, target, relation_type) VALUES (?, ?, ?)", 
                             (r['source'], r['target'], r['relation_type']))
            results.append(f"Saved {len(relations)} relations")
            
        if observations:
            for o in observations:
                conn.execute("INSERT INTO observations (entity_name, content) VALUES (?, ?)", 
                             (o['entity_name'], o['content']))
            results.append(f"Saved {len(observations)} observations")
        
        conn.commit()
    finally:
        conn.close()

    if bank_files:
        bank_dir = get_bank_dir()
        for filename, content in bank_files.items():
            if not filename.endswith(".md"):
                filename += ".md"
            path = os.path.join(bank_dir, filename)
            async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
                await f.write(content)
        results.append(f"Updated {len(bank_files)} bank files")

    return " | ".join(results) if results else "No data provided."

@mcp.tool()
async def read_memory(query: Optional[str] = None, scope: str = "all"):
    """
    Unified read tool for both Knowledge Graph and Memory Bank.
    - query: Search term (optional)
    - scope: "all", "graph", or "bank"
    """
    response = {}
    
    # 1. READ GRAPH
    if scope in ["all", "graph"]:
        conn = sqlite3.connect(get_db_path())
        try:
            cursor = conn.cursor()
            if query:
                q = f"%{query}%"
                e_matches = cursor.execute("SELECT * FROM entities WHERE name LIKE ? OR description LIKE ?", (q, q)).fetchall()
                o_matches = cursor.execute("SELECT * FROM observations WHERE content LIKE ?", (q,)).fetchall()
                response["graph"] = {
                    "entities": [{"name": e[0], "type": e[1], "description": e[2]} for e in e_matches],
                    "observations": [{"entity": o[1], "content": o[2], "at": o[3]} for o in o_matches]
                }
            else:
                entities = cursor.execute("SELECT * FROM entities").fetchall()
                relations = cursor.execute("SELECT * FROM relations").fetchall()
                obs = cursor.execute("SELECT * FROM observations").fetchall()
                response["graph"] = {
                    "entities": [{"name": e[0], "type": e[1], "description": e[2]} for e in entities],
                    "relations": [{"source": r[0], "target": r[1], "type": r[2]} for r in relations],
                    "observations": [{"entity": o[1], "content": o[2], "at": o[3]} for o in obs]
                }
        finally:
            conn.close()

    # 2. READ BANK
    if scope in ["all", "bank"]:
        bank_dir = get_bank_dir()
        bank_data = {}
        if os.path.exists(bank_dir):
            for filename in os.listdir(bank_dir):
                if filename.endswith(".md"):
                    path = os.path.join(bank_dir, filename)
                    async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
                        content = await f.read()
                        if not query or query.lower() in content.lower():
                            bank_data[filename] = content
            response["bank"] = bank_data

    return response

@mcp.tool()
def delete_memory(entities: List[str]):
    """Removes specific entities and their associated data from the Knowledge Graph."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for name in entities:
            conn.execute("DELETE FROM entities WHERE name = ?", (name,))
        conn.commit()
        return f"Deleted {len(entities)} entities and all related observations/relations."
    finally:
        conn.close()

# --- INITIALIZATION ---
def main():
    init_db()
    import asyncio
    asyncio.run(initialize_bank())
    mcp.run()

if __name__ == "__main__":
    main()
