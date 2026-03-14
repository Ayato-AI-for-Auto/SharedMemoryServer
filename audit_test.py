import sqlite3
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from shared_memory.server import init_db, create_entities, create_relations, add_observations, delete_entities, read_graph

def test_audit():
    db_path = "audit_test.db"
    if os.path.exists(db_path): os.remove(db_path)
    os.environ["MEMORY_DB_PATH"] = db_path
    
    print("Initializng DB...")
    init_db()
    
    print("Creating entity 'Agent' and 'Skill'...")
    create_entities([
        {"name": "Agent", "entity_type": "actor", "description": "The AI Agent"},
        {"name": "Skill", "entity_type": "capability", "description": "A tool"}
    ])
    
    print("Creating relation 'Agent' -> 'Skill'...")
    create_relations([{"source": "Agent", "target": "Skill", "relation_type": "uses"}])
    
    print("Adding observation to 'Agent'...")
    add_observations([{"entity_name": "Agent", "content": "Agent is active"}])
    
    graph_before = read_graph()
    print(f"Graph Status Before Delete: Entities={len(graph_before['entities'])}, Relations={len(graph_before['relations'])}, Obs={len(graph_before['observations'])}")
    
    print("Deleting entity 'Agent' (Should trigger CASCADE)...")
    delete_entities(["Agent"])
    
    graph_after = read_graph()
    print(f"Graph Status After Delete: Entities={len(graph_after['entities'])}, Relations={len(graph_after['relations'])}, Obs={len(graph_after['observations'])}")
    
    # Assertions
    if len(graph_after['relations']) == 0 and len(graph_after['observations']) == 0:
        print("✅ CASCADE TEST PASSED: Relations and Observations were automatically cleaned up.")
    else:
        print("❌ CASCADE TEST FAILED: Relations or Observations still exist.")
        sys.exit(1)

    if os.path.exists(db_path): os.remove(db_path)

if __name__ == "__main__":
    test_audit()
