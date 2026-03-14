import unittest
import sqlite3
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from shared_memory.server import init_db, create_entities, create_relations, add_observations, read_graph, search_nodes

class TestGraphOps(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_memory.db"
        os.environ["MEMORY_DB_PATH"] = self.db_path
        init_db()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_entity_crud(self):
        # Create
        create_entities([{"name": "test_node", "entity_type": "test_type", "description": "test_desc"}])
        
        # Read
        graph = read_graph()
        self.assertEqual(len(graph["entities"]), 1)
        self.assertEqual(graph["entities"][0]["name"], "test_node")

        # Search
        matches = search_nodes("test_node")
        self.assertEqual(len(matches["entity_matches"]), 1)

    def test_relations_and_observations(self):
        create_entities([
            {"name": "A", "entity_type": "typeA"},
            {"name": "B", "entity_type": "typeB"}
        ])
        create_relations([{"source": "A", "target": "B", "relation_type": "linked_to"}])
        add_observations([{"entity_name": "A", "content": "fact about A"}])

        graph = read_graph()
        self.assertEqual(len(graph["relations"]), 1)
        self.assertEqual(len(graph["observations"]), 1)

if __name__ == "__main__":
    unittest.main()
