import os
import aiofiles
import pickle
import numpy as np
import math
from typing import List, Optional, Dict
from fastmcp import FastMCP

import json
import datetime

try:
    from .utils import log_error, get_bank_dir, mask_sensitive_data
    from .database import get_connection, init_db, update_access
    from .logic import batch_cosine_similarity, calculate_importance
    from .embeddings import get_gemini_client, compute_embedding, EMBEDDING_MODEL
except (ImportError, ValueError):
    import sys
    import os

    # Ensure package directory is in sys.path for direct execution
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    if _current_dir not in sys.path:
        sys.path.insert(0, _current_dir)
    from utils import log_error, get_bank_dir, mask_sensitive_data
    from database import get_connection, init_db, update_access
    from logic import batch_cosine_similarity, calculate_importance
    from embeddings import get_gemini_client, compute_embedding, EMBEDDING_MODEL

mcp = FastMCP("SharedMemoryServer")


async def _check_conflict(entity_name: str, new_content: str, agent_id: str):
    """
    Internal helper to check if new content contradicts existing observations using LLM.
    Returns (conflict_found: bool, reason: str)
    """
    conn = get_connection()
    try:
        # Fetch up to 3 most recent observations for context
        existing = conn.execute(
            "SELECT content FROM observations WHERE entity_name = ? ORDER BY timestamp DESC LIMIT 3",
            (entity_name,),
        ).fetchall()
        if not existing:
            return False, None

        existing_text = "\n".join([f"- {row[0]}" for row in existing])
        prompt = (
            f"You are a Fact-Checking Engine. Check if the following NEW statement contradicts "
            f"the EXISTING knowledge about '{entity_name}'.\n\n"
            f"EXISTING KNOWLEDGE:\n{existing_text}\n\n"
            f"NEW STATEMENT:\n{new_content}\n\n"
            f"Is there a direct contradiction? Respond ONLY with a JSON object:\n"
            f'{{"conflict": true/false, "reason": "explanation if true, else empty"}}'
        )

        client = get_gemini_client()
        if not client:
            return False, None

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
        ).text

        # Parse JSON from response (handling potential markdown formatting)
        clean_res = response.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_res)

        if data.get("conflict"):
            # Log to DB
            conn.execute(
                "INSERT INTO conflicts (entity_name, existing_content, new_content, reason, agent_id) VALUES (?, ?, ?, ?, ?)",
                (entity_name, existing_text, new_content, data.get("reason"), agent_id),
            )
            conn.commit()
            return True, data.get("reason")

        return False, None
    except Exception as e:
        log_error(f"Conflict check failed for {entity_name}", e)
        return False, None
    finally:
        conn.close()


# --- MEMORY BANK STORAGE (Markdown) ---
BANK_FILES = {
    "projectBrief.md": "Core requirements and goals.",
    "productContext.md": "Why this project exists and its scope.",
    "activeContext.md": "What we are working on now and recent decisions.",
    "systemPatterns.md": "Architecture, design patterns, and technical decisions.",
    "techContext.md": "Tech stack, dependencies, and constraints.",
    "progress.md": "Status, roadmap, and what's next.",
    "decisionLog.md": "Record of significant technical choices.",
}


async def initialize_bank():
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir)
    for filename, description in BANK_FILES.items():
        path = os.path.join(bank_dir, filename)
        if not os.path.exists(path):
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(
                    f"# {filename}\n\n{description}\n\n## Status\n- Initialized\n"
                )


# --- UNIFIED TOOLS (V2 API) ---


@mcp.tool()
async def save_memory(
    entities: Optional[List[Dict[str, str]]] = None,
    relations: Optional[List[Dict[str, str]]] = None,
    observations: Optional[List[Dict[str, str]]] = None,
    bank_files: Optional[Dict[str, str]] = None,
    agent_id: str = "default_agent",
):
    """
    Unified write tool for both Knowledge Graph and Memory Bank.

    PURPOSE:
    - Use this to persist new facts, relationships, and documents.
    - It acts as the primary entry point for 'learning' and 'recording' project state.

    CATEGORIES OF DATA:
    1. entities: Fundamental concepts, tools, or markers (e.g., "Python", "Requirement-01").
    2. relations: Semantic links between entities (e.g., "A" -- "implements" --> "B").
    3. observations: Fragmented factual statements about an entity (e.g., "Feature X is deprecated").
    4. bank_files: Markdown documents for long-form context.

    BUSINESS LOGIC:
    - Automatically updates entity 'importance' on access (Observations/Bank).
    - Triggers 'Semantic Conflict Detection' on observations to prevent contradictory knowledge.
    - Synchronizes bank_files between SQLite (mirror) and physical disk.
    - Automatically detects 'mentions' of existing entities within bank_files and creates relations.

    GUIDELINES:
    - agent_id: Always provide a descriptive ID (e.g., your agent name or session ID) for attribution.
    - importance: Set 1-10 (default 5). Higher for core architectural decisions.
    """
    results = []
    conflicts_found = []

    conn = get_connection()
    try:
        # 0. Data Validation (Phase 2 Hardening)
        if entities:
            for e in entities:
                if not e.get("name"):
                    raise ValueError("Entity 'name' is required and cannot be empty.")
                if "importance" in e:
                    try:
                        imp = int(e["importance"])
                        if not (1 <= imp <= 10):
                            raise ValueError(f"Importance for '{e['name']}' must be between 1 and 10.")
                    except (TypeError, ValueError) as ve:
                        raise ValueError(f"Invalid importance value for '{e['name']}': {e['importance']}. Must be an integer 1-10.") from ve
        
        if relations:
            for r in relations:
                if not r.get("source") or not r.get("target") or not r.get("relation_type"):
                    raise ValueError("Relation requires 'source', 'target', and 'relation_type'.")
        
        if observations:
            for o in observations:
                if not o.get("entity_name") or not o.get("content"):
                    raise ValueError("Observation requires 'entity_name' and 'content'.")

        # 1. Save Entities
        if entities:
            for e in entities:
                name = e["name"]
                e_type = e.get("entity_type", "concept")
                desc = e.get("description", "")
                importance = e.get("importance", 5)

                # Audit: Fetch old state
                old_row = conn.execute(
                    "SELECT name, entity_type, description FROM entities WHERE name = ?",
                    (name,),
                ).fetchone()

                # INSERT OR REPLACE
                conn.execute(
                    "INSERT OR REPLACE INTO entities (name, entity_type, description, importance, updated_by) VALUES (?, ?, ?, ?, ?)",
                    (name, e_type, desc, importance, agent_id),
                )

                # Record Audit
                action = "UPDATE" if old_row else "INSERT"
                old_data = (
                    json.dumps(
                        {"name": old_row[0], "type": old_row[1], "desc": old_row[2]}
                    )
                    if old_row
                    else None
                )
                new_data = json.dumps({"name": name, "type": e_type, "desc": desc})
                conn.execute(
                    "INSERT INTO audit_logs (table_name, content_id, action, old_data, new_data, agent_id) VALUES (?, ?, ?, ?, ?, ?)",
                    ("entities", name, action, old_data, new_data, agent_id),
                )

                # Vectorize
                vector = await compute_embedding(f"{name} ({e_type}): {desc}")
                if vector:
                    import pickle

                    conn.execute(
                        "INSERT OR REPLACE INTO embeddings (content_id, vector, model_name) VALUES (?, ?, ?)",
                        (name, pickle.dumps(vector), EMBEDDING_MODEL),
                    )
            results.append(f"Saved {len(entities)} entities")

        # 2. Save Relations
        if relations:
            relation_tuples = [
                (r["source"], r["target"], r["relation_type"], agent_id)
                for r in relations
            ]
            conn.executemany(
                "INSERT OR REPLACE INTO relations (source, target, relation_type, created_by) VALUES (?, ?, ?, ?)",
                relation_tuples,
            )
            results.append(f"Saved {len(relations)} relations")

        # 3. Save Observations & Conflict Check
        if observations:
            for o in observations:
                entity_name = o["entity_name"]
                content = mask_sensitive_data(o["content"])

                # Semantic Conflict Detection (Phase 13)
                is_conflict, reason = await _check_conflict(
                    entity_name, content, agent_id
                )
                if is_conflict:
                    conflicts_found.append({"entity": entity_name, "reason": reason})

                conn.execute(
                    "INSERT INTO observations (entity_name, content, created_by) VALUES (?, ?, ?)",
                    (entity_name, content, agent_id),
                )
                # Boost importance
                conn.execute(
                    "UPDATE entities SET importance = MIN(importance + 1, 10), updated_at = CURRENT_TIMESTAMP WHERE name = ?",
                    (entity_name,),
                )
                # Audit
                conn.execute(
                    "INSERT INTO audit_logs (table_name, content_id, action, new_data, agent_id) VALUES (?, ?, ?, ?, ?)",
                    (
                        "observations",
                        entity_name,
                        "INSERT",
                        json.dumps({"content": content}),
                        agent_id,
                    ),
                )
            results.append(f"Saved {len(observations)} observations")

        # 4. Save Bank Files & Sync
        if bank_files:
            existing_entities = [
                r[0] for r in conn.execute("SELECT name FROM entities").fetchall()
            ]
            bank_dir = get_bank_dir()
            for filename, content in bank_files.items():
                if not filename.endswith(".md"):
                    filename += ".md"
                content = mask_sensitive_data(content)

                # DB Sync
                old_content = conn.execute(
                    "SELECT content FROM bank_files WHERE filename = ?", (filename,)
                ).fetchone()
                old_data = (
                    json.dumps({"content": old_content[0]}) if old_content else None
                )
                conn.execute(
                    "INSERT OR REPLACE INTO bank_files (filename, content, updated_by) VALUES (?, ?, ?)",
                    (filename, content, agent_id),
                )
                conn.execute(
                    "INSERT INTO audit_logs (table_name, content_id, action, old_data, new_data, agent_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        "bank_files",
                        filename,
                        "UPDATE" if old_content else "INSERT",
                        old_data,
                        json.dumps({"content": content}),
                        agent_id,
                    ),
                )

                # Disk Sync
                path = os.path.join(bank_dir, filename)
                import aiofiles

                async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                    await f.write(content)

                # Mentions Detection
                for entity_name in existing_entities:
                    if entity_name.lower() in content.lower():
                        conn.execute(
                            "INSERT OR REPLACE INTO relations (source, target, relation_type, created_by) VALUES (?, ?, ?, ?)",
                            (filename, entity_name, "mentions", agent_id),
                        )
            results.append(f"Updated {len(bank_files)} bank files")

        conn.commit()

        status_msg = " | ".join(results)
        response = {"status": "success", "message": status_msg}
        if conflicts_found:
            response["conflicts_detected"] = conflicts_found
            response["warning"] = "Semantic contradictions were detected."

        return response

    except Exception as e:
        log_error("Failed to save memory", e)
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_conflicts(entity_name: Optional[str] = None):
    """
    Retrieves unresolved semantic contradictions detected during 'save_memory'.

    PURPOSE:
    - Use this to review knowledge gaps or 'hallucination' risks where new data conflicts with old.
    - Part of the 'Agent-in-the-Loop' resolution pattern: You should call this if save_memory warns about conflicts.

    OUTPUT:
    - Returns a list of conflicts including existing_content, new_content, and the LLM's 'reason' for flagging it.
    """
    conn = get_connection()
    try:
        if entity_name:
            cursor = conn.execute(
                "SELECT id, entity_name, existing_content, new_content, reason, detected_at FROM conflicts WHERE entity_name = ? AND resolved = 0",
                (entity_name,),
            )
        else:
            cursor = conn.execute(
                "SELECT id, entity_name, existing_content, new_content, reason, detected_at FROM conflicts WHERE resolved = 0"
            )

        conflicts = []
        for row in cursor.fetchall():
            conflicts.append(
                {
                    "id": row[0],
                    "entity": row[1],
                    "existing": row[2],
                    "new": row[3],
                    "reason": row[4],
                    "at": row[5],
                }
            )
        return conflicts
    finally:
        conn.close()


@mcp.tool()
async def read_memory(query: Optional[str] = None, scope: str = "all"):
    """
    Unified search and retrieval tool for Knowledge Graph and Memory Bank.

    PURPOSE:
    - Navigating the codebase context, finding existing rules, or retrieving project history.

    SEARCH MODES:
    - Keyword Search: Standard SQLite LIKE matching.
    - Semantic Search: Automatically triggered if 'query' is provided. Uses Gemini embeddings for meaning-based hits.
    - 1-hop Expansion: Automatically retrieves neighbors of hit entities to provide 'spreading activation' context.

    SCOPE:
    - "all": (Default) Returns both graph nodes and bank file contents.
    - "graph": Focus only on entities, relations, and observations.
    - "bank": Focus only on Markdown documents.
    """
    response = {}

    # 1. READ GRAPH
    if scope in ["all", "graph"]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if query:
                q = f"%{query}%"
                e_matches = cursor.execute(
                    "SELECT * FROM entities WHERE name LIKE ? OR description LIKE ?",
                    (q, q),
                )
                e_rows = e_matches.fetchall()

                o_matches = cursor.execute(
                    "SELECT * FROM observations WHERE content LIKE ?", (q,)
                ).fetchall()
                for row in e_rows:
                    update_access(row[0])
                # 1-hop Graph Expansion
                matched_names = [r[0] for r in e_rows]
                if matched_names:
                    # Find all relations connected to matched entities
                    placeholders = ",".join(["?"] * len(matched_names))
                    relations = cursor.execute(
                        f"SELECT * FROM relations WHERE source IN ({placeholders}) OR target IN ({placeholders})",
                        matched_names + matched_names,
                    ).fetchall()

                    # Collect connected entities not already matched
                    connected_names = set()
                    for r in relations:
                        if r[0] not in matched_names:
                            connected_names.add(r[0])
                        if r[1] not in matched_names:
                            connected_names.add(r[1])

                    if connected_names:
                        c_placeholders = ",".join(["?"] * len(connected_names))
                        c_entities = cursor.execute(
                            f"SELECT * FROM entities WHERE name IN ({c_placeholders})",
                            list(connected_names),
                        ).fetchall()
                        c_obs = cursor.execute(
                            f"SELECT * FROM observations WHERE entity_name IN ({c_placeholders})",
                            list(connected_names),
                        ).fetchall()

                        # Merge into response
                        all_entities = e_rows + c_entities
                        all_obs = o_matches + c_obs
                    else:
                        all_entities = e_rows
                        all_obs = o_matches
                else:
                    all_entities = e_rows
                    all_obs = o_matches
                    relations = []

                response["graph"] = {
                    "entities": [
                        {"name": r[0], "type": r[1], "description": r[2]}
                        for r in all_entities
                    ],
                    "relations": [
                        {
                            "source": r[0],
                            "target": r[1],
                            "type": r[2],
                            "justification": r[3],
                        }
                        for r in relations
                    ],
                    "observations": [
                        {"entity": o[1], "content": o[2], "at": o[3]} for o in all_obs
                    ],
                }
            else:
                entities = cursor.execute("SELECT * FROM entities").fetchall()
                relations = cursor.execute("SELECT * FROM relations").fetchall()
                obs = cursor.execute("SELECT * FROM observations").fetchall()
                response["graph"] = {
                    "entities": [
                        {"name": e[0], "type": e[1], "description": e[2]}
                        for e in entities
                    ],
                    "relations": [
                        {
                            "source": r[0],
                            "target": r[1],
                            "type": r[2],
                            "justification": r[3],
                        }
                        for r in relations
                    ],
                    "observations": [
                        {"entity": o[1], "content": o[2], "at": o[3]} for o in obs
                    ],
                }
        except Exception as e:
            log_error("Failed to read knowledge graph", e)
            response["graph_error"] = str(e)
        finally:
            conn.close()

    # 2. READ BANK (with DB recovery)
    if scope in ["all", "bank"]:
        bank_dir = get_bank_dir()
        bank_data = {}
        found_files = set()

        # Try reading from physical disk first
        if os.path.exists(bank_dir):
            for filename in os.listdir(bank_dir):
                if filename.endswith(".md"):
                    path = os.path.join(bank_dir, filename)
                    try:
                        async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
                            content = await f.read()
                            if not query or query.lower() in content.lower():
                                bank_data[filename] = content
                                found_files.add(filename)
                                update_access(filename)
                    except Exception as e:
                        log_error(f"Failed to read bank file {filename}", e)

        # Fallback/Supplemental: Read from DB mirror
        conn = get_connection()
        try:
            cursor = conn.cursor()
            db_files = cursor.execute(
                "SELECT filename, content FROM bank_files"
            ).fetchall()
            for filename, content in db_files:
                if filename not in found_files:
                    if not query or query.lower() in content.lower():
                        bank_data[f"{filename} [RECOVERED]"] = content
        except Exception as e:
            log_error("Failed to read bank/mirror from database", e)
        finally:
            conn.close()

        response["bank"] = bank_data

    # 3. SEMANTIC SEARCH (Hybrid Reranking with Batching Optimization)
    if query and get_gemini_client():
        query_vector = await compute_embedding(query)
        if query_vector:
            conn = get_connection()
            try:
                cursor = conn.cursor()
                rows = cursor.execute(
                    "SELECT content_id, vector, model_name FROM embeddings"
                ).fetchall()
                if rows:
                    cids = [r[0] for r in rows]
                    vectors = np.array([pickle.loads(r[1]) for r in rows])
                    scores = batch_cosine_similarity(query_vector, vectors)

                    semantic_results = list(zip(cids, scores))

                    # Get importance scores and stability
                    metadata = cursor.execute(
                        "SELECT content_id, access_count, last_accessed, stability FROM knowledge_metadata"
                    ).fetchall()
                    importance_map = {
                        m[0]: calculate_importance(m[1], m[2], m[3]) for m in metadata
                    }

                    # Associative Priming: Boost neighbors of matched entities
                    primed_ids = set()
                    if "graph" in response and "relations" in response["graph"]:
                        for rel in response["graph"]["relations"]:
                            # If source or target is a strong semantic hit, prime the other
                            primed_ids.add(rel["source"])
                            primed_ids.add(rel["target"])

                    # Hybrid ranking: Similarity * Importance (+ Priming Boost)
                    hybrid_results = []
                    for cid, score in semantic_results:
                        imp_weight = importance_map.get(cid, 1.1)
                        # Priming boost: +20% importance if the item is related to a direct hit
                        prime_boost = 1.2 if cid in primed_ids else 1.0

                        final_score = (
                            score * (0.8 + 0.2 * math.log1p(imp_weight)) * prime_boost
                        )
                        hybrid_results.append(
                            (cid, final_score, score, imp_weight, cid in primed_ids)
                        )

                    hybrid_results.sort(key=lambda x: x[1], reverse=True)
                    response["semantic_hits"] = [
                        {
                            "id": r[0],
                            "score": round(float(r[1]), 4),
                            "base_similarity": round(float(r[2]), 4),
                            "importance": round(r[3], 2),
                            "primed": r[4],
                        }
                        for r in hybrid_results[:5]
                        if r[2] > 0.3
                    ]
            except Exception as e:
                log_error("Semantic search computation failed", e)
            finally:
                conn.close()

    return response


@mcp.tool()
def delete_memory(entities: List[str], agent_id: str = "default_agent"):
    """
    Removes specific entities and their associated data from the Knowledge Graph.

    PURPOSE:
    - Cleanup of obsolete or incorrect concepts.

    SIDE EFFECTS (CASCADE):
    - Automatically deletes all related 'observations' and 'relations' (where the entity is source or target).
    - Removes associated 'embeddings' and 'knowledge_metadata'.
    - Note: This does NOT delete bank_files, but may break 'mentions' links.
    """
    conn = get_connection()
    try:
        for name in entities:
            # Audit: Save old state before deletion
            old_row = conn.execute(
                "SELECT name, entity_type, description FROM entities WHERE name = ?",
                (name,),
            ).fetchone()
            if old_row:
                old_data = json.dumps(
                    {"name": old_row[0], "type": old_row[1], "desc": old_row[2]}
                )
                conn.execute(
                    "INSERT INTO audit_logs (table_name, content_id, action, old_data, agent_id) VALUES (?, ?, ?, ?, ?)",
                    ("entities", name, "DELETE", old_data, agent_id),
                )
            conn.execute("DELETE FROM entities WHERE name = ?", (name,))
        conn.commit()
        return f"Deleted {len(entities)} entities and recorded in audit logs."
    except Exception as e:
        log_error(f"Failed to delete entities: {entities}", e)
        return f"Error: Deletion failed: {e}"
    finally:
        conn.close()


@mcp.tool()
def get_audit_history(content_id: str):
    """
    Retrieves the change history for a specific entity or bank file.

    PURPOSE:
    - Tracking the evolution of a concept or identifying who introduced a specific fact.
    - Essential for 'rollback_memory': Use this tool first to find the 'id' of the state you wish to restore.

    OUTPUT:
    - A list of audit log entries: (id, table, action, old_data, new_data, timestamp, agent_id).
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT action, old_data, new_data, agent_id, timestamp FROM audit_logs WHERE content_id = ? ORDER BY timestamp DESC",
            (content_id,),
        )
        history = []
        for row in cursor.fetchall():
            history.append(
                {
                    "action": row[0],
                    "old": json.loads(row[1]) if row[1] else None,
                    "new": json.loads(row[2]) if row[2] else None,
                    "agent": row[3],
                    "timestamp": row[4],
                }
            )
        return history
    finally:
        conn.close()


@mcp.tool()
async def get_memory_map(focus_entity: Optional[str] = None):
    """
    Generates a Mermaid.js diagram of the knowledge graph.

    PURPOSE:
    - Visualizing the structure of your project's knowledge.
    - Use focus_entity to zoom into a specific area (1-hop connections).

    AI GUIDANCE:
    - If the diagram is too large, use focus_entity to isolate specific sub-graphs.
    - You can use this to explain the system's architecture or dependencies to the user.
    """
    conn = get_connection()
    try:
        if focus_entity:
            # 1-hop neighborhood
            relations = conn.execute(
                "SELECT source, target, relation_type FROM relations WHERE source = ? OR target = ?",
                (focus_entity, focus_entity),
            ).fetchall()
        else:
            # Full graph (limited to 100 relations to avoid bloat)
            relations = conn.execute(
                "SELECT source, target, relation_type FROM relations LIMIT 100"
            ).fetchall()

        if not relations:
            return "No relations found to map."

        mermaid_lines = ["graph TD"]
        for src, tgt, rel in relations:
            # Escape strings for Mermaid
            src_e = f'"{src}"'
            tgt_e = f'"{tgt}"'
            mermaid_lines.append(f"    {src_e} -- {rel} --> {tgt_e}")

        return "\n".join(mermaid_lines)
    except Exception as e:
        log_error("Failed to generate memory map", e)
        return f"Error: {e}"
    finally:
        conn.close()


@mcp.tool()
async def synthesize_knowledge(entity_name: str):
    """
    Consolidates all fragmented observations and relations for an entity into a coherent summary.

    PURPOSE:
    - Gaining a deep understanding of a complex entity without reading hundreds of raw observations.
    - Creating Wiki-style reports for the project.

    BUSINESS LOGIC:
    - Uses Gemini LLM to synthesize data into a structured Markdown format.
    - Highly effective for entities that have evolved significantly over time.
    """
    conn = get_connection()
    try:
        # 1. Fetch entity info
        entity = conn.execute(
            "SELECT entity_type, description FROM entities WHERE name = ?",
            (entity_name,),
        ).fetchone()
        if not entity:
            return f"Entity '{entity_name}' not found."

        # 2. Fetch all observations
        obs = conn.execute(
            "SELECT content FROM observations WHERE entity_name = ?", (entity_name,)
        ).fetchall()

        # 3. Fetch all relations
        rels = conn.execute(
            "SELECT target, relation_type FROM relations WHERE source = ?",
            (entity_name,),
        ).fetchall()
        rels_in = conn.execute(
            "SELECT source, relation_type FROM relations WHERE target = ?",
            (entity_name,),
        ).fetchall()

        # 4. Prepare context for LLM
        context = [
            f"Entity: {entity_name} ({entity[0]})",
            f"Base Description: {entity[1]}",
            "\nObservations:",
        ]
        context.extend([f"- {o[0]}" for o in obs])
        context.append("\nRelations (Outgoing):")
        context.extend([f"- {entity_name} {r[1]} {r[0]}" for r in rels])
        context.append("\nRelations (Incoming):")
        context.extend([f"- {r[0]} {r[1]} {entity_name}" for r in rels_in])

        prompt = (
            "You are a Knowledge Synthesis Engine. Based on the following fragmented data, "
            "provide a concise, highly structured Wiki-style summary (about 2-3 paragraphs) "
            "that represents the current status and essential knowledge of this entity.\n\n"
            + "\n".join(context)
        )

        # 5. Call LLM
        client = get_gemini_client()
        if not client:
            return f"Synthesis failed: Google API client not configured.\n\nContext gathered:\n{chr(10).join(context)}"

        # Using compute_embedding logic pattern or similar?
        # Actually need to call generate_content
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
        )

        return f"### Knowledge Synthesis: {entity_name}\n\n{response.text}"

    except Exception as e:
        log_error(f"Synthesis failed for {entity_name}", e)
        return f"Error: {e}"
    finally:
        conn.close()


@mcp.tool()
def rollback_memory(audit_id: int):
    """
    Restores an entry to its state in a specific audit log record.

    PURPOSE:
    - Reverting accidental deletions or incorrect updates.

    GUIDELINES:
    - Use 'get_audit_history' to find the correct audit_id before calling this.
    - WARNING: This will overwrite the current state with the historical 'old_data' from the log.
    """
    conn = get_connection()
    try:
        log = conn.execute(
            "SELECT table_name, content_id, old_data FROM audit_logs WHERE id = ?",
            (audit_id,),
        ).fetchone()
        if not log or not log[2]:
            return "Error: Audit record not found or has no 'old_data' to restore."

        table, cid, data_raw = log
        data = json.loads(data_raw)

        if table == "entities":
            conn.execute(
                "INSERT OR REPLACE INTO entities (name, entity_type, description) VALUES (?, ?, ?)",
                (data["name"], data["type"], data["desc"]),
            )
        elif table == "bank_files":
            conn.execute(
                "INSERT OR REPLACE INTO bank_files (filename, content, last_synced) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (cid, data["content"]),
            )

        conn.commit()
        return f"Successfully rolled back {cid} in {table}."
    except Exception as e:
        log_error(f"Rollback failed for audit_id {audit_id}", e)
        return f"Error: Rollback failed: {e}"
    finally:
        conn.close()


@mcp.tool()
async def create_snapshot(name: str, description: str = ""):
    """
    Creates a full snapshot (backup) of the current knowledge base.

    PURPOSE:
    - Creating a recovery point before major refactors or deletions.
    - Marking a 'milestone' in the project history.

    OUTPUT:
    - Returns the snapshot ID, which can be used later with 'restore_snapshot'.
    """
    import shutil
    from .utils import get_db_path

    db_path = get_db_path()
    snapshot_dir = os.path.join(os.path.dirname(db_path), "snapshots")
    if not os.path.exists(snapshot_dir):
        os.makedirs(snapshot_dir)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_file = os.path.join(snapshot_dir, f"snapshot_{ts}.db")

    try:
        shutil.copy2(db_path, snapshot_file)
        conn = get_connection()
        conn.execute(
            "INSERT INTO snapshots (name, description, file_path) VALUES (?, ?, ?)",
            (name, description, snapshot_file),
        )
        conn.commit()
        conn.close()
        return f"Snapshot '{name}' created at {snapshot_file}"
    except Exception as e:
        log_error("Failed to create snapshot", e)
        return f"Error: Snapshot failed: {e}"


@mcp.tool()
async def restore_snapshot(snapshot_id: int):
    """
    Restores the entire knowledge base from a specific snapshot.

    PURPOSE:
    - Recovering from catastrophic information loss or experimental failures.

    WARNING:
    - This is a DESTRUCTIVE operation. It replaces the entire current database with the snapshot data.
    - Always create a fresh snapshot before performing a restore if you have unsaved work.
    """
    import shutil
    from .utils import get_db_path

    conn = get_connection()
    row = conn.execute(
        "SELECT file_path FROM snapshots WHERE id = ?", (snapshot_id,)
    ).fetchone()
    conn.close()

    if not row:
        return f"Error: Snapshot ID {snapshot_id} not found."

    snapshot_file = row[0]
    db_path = get_db_path()

    try:
        shutil.copy2(snapshot_file, db_path)
        return f"Successfully restored database from snapshot at {snapshot_file}"
    except Exception as e:
        log_error("Failed to restore snapshot", e)
        return f"Error: Restore failed: {e}"


@mcp.tool()
async def repair_memory():
    """
    Syncs mirrored content from SQLite back to the physical Markdown files.

    PURPOSE:
    - Recovering lost .md files or correcting desynchronization between the DB and disk.
    - Ensuring the physical 'memory-bank/' matches the digital 'brain'.
    """
    results = []
    bank_dir = get_bank_dir()
    if not os.path.exists(bank_dir):
        os.makedirs(bank_dir)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        files = cursor.execute("SELECT filename, content FROM bank_files").fetchall()
        count = 0
        for filename, content in files:
            path = os.path.join(bank_dir, filename)
            async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
                await f.write(content)
            count += 1
        results.append(f"Restored {count} files from DB to disk.")
    except Exception as e:
        log_error("Memory repair (DB to Disk) failed", e)
        results.append(f"Error: Repair failed: {e}")
    finally:
        conn.close()
    return " | ".join(results)


@mcp.tool()
async def archive_memory(threshold: float = 0.1):
    """
    Archives low-importance knowledge that falls below the importance threshold.

    PURPOSE:
    - Improving AI performance and reducing 'noise' in search results.
    - Moving 'cold' data to an inactive state.

    BUSINESS LOGIC:
    - Entities with 'importance' < threshold (taking 'decay' into account) will be marked as archived.
    - Archived items are excluded from standard 'read_memory' searches.
    """
    conn = get_connection()
    results = []
    try:
        cursor = conn.cursor()
        metadata = cursor.execute(
            "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
        ).fetchall()

        to_archive = []
        for cid, count, last in metadata:
            score = calculate_importance(count, last)
            if score < threshold:
                to_archive.append(cid)

        if to_archive:
            # For simplicity in this version, we mark them as archived in the description
            for cid in to_archive:
                cursor.execute(
                    "UPDATE entities SET description = '[ARCHIVED] ' || description WHERE name = ? AND description NOT LIKE '[ARCHIVED]%'",
                    (cid,),
                )
            results.append(
                f"Archived {len(to_archive)} items with importance below {threshold}"
            )
        else:
            results.append("No items found below the importance threshold.")

        conn.commit()
    except Exception as e:
        log_error("Memory archival failed", e)
        results.append(f"Error: Archival failed: {e}")
    finally:
        conn.close()
    return " | ".join(results)


@mcp.tool()
async def get_memory_health():
    """
    Returns diagnostic information about the health and state of the knowledge base.

    PURPOSE:
    - Self-diagnosis and identifying areas where the knowledge graph is weak or 'thin'.
    - Checking if semantic search is fully functional (embedding coverage).

    METRICS INCLUDED:
    - Entity count, relation density, embedding coverage, and importance distribution.
    - AI-generated assessment of 'Knowledge Gaps' or 'Biases'.
    """
    conn = get_connection()
    health = {}
    try:
        cursor = conn.cursor()
        health["entities_count"] = cursor.execute(
            "SELECT COUNT(*) FROM entities"
        ).fetchone()[0]
        health["relations_count"] = cursor.execute(
            "SELECT COUNT(*) FROM relations"
        ).fetchone()[0]
        health["observations_count"] = cursor.execute(
            "SELECT COUNT(*) FROM observations"
        ).fetchone()[0]
        health["bank_files_cached"] = cursor.execute(
            "SELECT COUNT(*) FROM bank_files"
        ).fetchone()[0]
        health["embeddings_count"] = cursor.execute(
            "SELECT COUNT(*) FROM embeddings"
        ).fetchone()[0]

        # Importance distribution
        metadata = cursor.execute(
            "SELECT content_id, access_count, last_accessed FROM knowledge_metadata"
        ).fetchall()
        if metadata:
            scores = [calculate_importance(m[1], m[2]) for m in metadata]
            health["importance_stats"] = {
                "avg": round(sum(scores) / len(scores), 2),
                "std_dev": round(float(np.std(scores)), 2),
                "max": round(max(scores), 2),
                "min": round(min(scores), 2),
            }
            health["archive_candidates_count"] = sum(1 for s in scores if s < 0.1)

        # Model distribution
        models = cursor.execute(
            "SELECT model_name, COUNT(*) FROM embeddings GROUP BY model_name"
        ).fetchall()
        health["model_distribution"] = {m[0]: m[1] for m in models}

        # Check for missing embeddings
        health["missing_embeddings"] = (
            health["entities_count"]
            + health["bank_files_cached"]
            - health["embeddings_count"]
        )

        # BYOK Check
        health["semantic_search_active"] = get_gemini_client() is not None

        # --- GAPS & BIAS DETECTION (Phase 11) ---
        # 1. Isolation Detection
        isolated = cursor.execute("""
            SELECT name FROM entities 
            WHERE name NOT IN (SELECT source FROM relations) 
            AND name NOT IN (SELECT target FROM relations)
        """).fetchall()
        health["gaps_analysis"] = {
            "isolated_entities_count": len(isolated),
            "isolated_entities": [i[0] for i in isolated[:10]],  # List first 10
        }

        # 2. Graph Density
        if health["entities_count"] > 1:
            max_relations = health["entities_count"] * (health["entities_count"] - 1)
            health["gaps_analysis"]["graph_density"] = round(
                health["relations_count"] / max_relations, 4
            )
        else:
            health["gaps_analysis"]["graph_density"] = 0

        # 3. Entity Type Distribution (Bias detection)
        type_dist = cursor.execute(
            "SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type"
        ).fetchall()
        health["bias_analysis"] = {t[0]: t[1] for t in type_dist}

        # Suggestion based on sparsity
        if len(type_dist) < 3:
            health["bias_analysis"]["warning"] = (
                "Low taxonomy diversity. Consider categorizing entities more granularly."
            )

        # 4. Agent Attribution Stats
        agent_stats = cursor.execute(
            "SELECT created_by, COUNT(*) FROM entities GROUP BY created_by"
        ).fetchall()
        health["agent_contribution"] = {
            a[0] if a[0] else "legacy": a[1] for a in agent_stats
        }

    except Exception as e:
        log_error("Health diagnostics failed", e)
        health["error"] = str(e)
    finally:
        conn.close()
    return health


# --- INITIALIZATION ---
def main():
    init_db()
    import asyncio

    asyncio.run(initialize_bank())
    mcp.run()


if __name__ == "__main__":
    main()
