from typing import List, Optional, Dict, Any
import json
import sqlite3
from shared_memory.utils import log_error
from shared_memory.database import get_connection
from shared_memory import graph, bank, search, management, troubleshooting, health
from shared_memory.exceptions import SharedMemoryError, DatabaseError


async def save_memory_core(
    entities: List[Dict[str, Any]] = [],
    relations: List[Dict[str, Any]] = [],
    observations: List[Dict[str, Any]] = [],
    bank_files: Dict[str, str] = {},
    agent_id: str = "default_agent",
) -> str:
    """
    Core logic for saving memory. Orchestrates graph and bank updates within a transaction.
    """
    conn = get_connection()
    results = []
    try:
        if entities:
            results.append(await graph.save_entities(entities, agent_id, conn))
        if relations:
            results.append(await graph.save_relations(relations, agent_id, conn))
        if observations:
            res, conflicts = await graph.save_observations(observations, agent_id, conn)
            results.append(res)
            if conflicts:
                results.append(f"CONFLICTS DETECTED: {json.dumps(conflicts)}")
        if bank_files:
            results.append(await bank.save_bank_files(bank_files, agent_id, conn))

        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        log_error("Database transaction failed in save_memory_core", e)
        raise DatabaseError(f"Transaction failed: {e}") from e
    except Exception as e:
        conn.rollback()
        log_error("Unexpected error in save_memory_core", e)
        raise SharedMemoryError(f"Unexpected error: {e}") from e
    finally:
        conn.close()
    return " | ".join(results)


async def read_memory_core(query: Optional[str] = None) -> Dict[str, Any]:
    """
    Core logic for reading memory.
    """
    try:
        if query:
            graph_data, bank_data = await search.perform_search(query)
        else:
            graph_data = await graph.get_graph_data()
            bank_data = await bank.read_bank_data()
        return {"graph": graph_data, "bank": bank_data}
    except Exception as e:
        log_error("Error in read_memory_core", e)
        raise SharedMemoryError(f"Read failed: {e}") from e


# Delegation proxies for management tools to keep server.py clean
async def get_audit_history_core(limit: int = 20, table_name: Optional[str] = None):
    return await management.get_audit_history_logic(limit, table_name)


async def synthesize_entity(entity_name: str):
    """Aggregates all known info about an entity into a master summary."""
    return await search.synthesize_knowledge(entity_name)


async def rollback_memory_core(audit_id: int):
    return await management.rollback_memory_logic(audit_id)


async def create_snapshot_core(name: str, description: str):
    return await management.create_snapshot_logic(name, description)


async def restore_snapshot_core(snapshot_id: int):
    return await management.restore_snapshot_logic(snapshot_id)


async def troubleshooting_record_core(problem, solution, env, tags):
    return await troubleshooting.save_troubleshooting_record(
        problem, solution, env, tags
    )


async def troubleshooting_search_core(query):
    return await troubleshooting.search_troubleshooting_history(query)


async def get_memory_health_core():
    # Mix basic management stats with deep diagnostics
    mgmt_health = await management.get_memory_health_logic()
    deep_health = await health.get_comprehensive_diagnostics()

    # Merge reports
    deep_health["management_stats"] = mgmt_health
    return deep_health


async def repair_memory_core():
    return await bank.repair_memory_logic()
