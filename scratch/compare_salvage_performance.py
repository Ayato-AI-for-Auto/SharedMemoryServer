import asyncio
import time
import json
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from shared_memory.cli.salvage import salvage_related_knowledge
from shared_memory.core.search import perform_search
from shared_memory.infra.database import init_db
from shared_memory.core.thought_logic import init_thoughts_db
from shared_memory.common.config import settings
from shared_memory.common.utils import get_db_path, get_thoughts_db_path

async def mock_perform_search_only(query: str, limit: int = 5):
    """リランクなしの高速検索(上位N件をそのまま返す)"""
    start = time.perf_counter()
    graph_data, bank_data = await perform_search(query, candidate_limit=limit)
    
    results = []
    for ent in graph_data.get("entities", []):
        results.append({"type": "entity", "id": ent["name"], "content": ent["description"]})
    for obs in graph_data.get("observations", []):
        results.append({"type": "observation", "id": obs["entity"], "content": obs["content"]})
    for filename, content in bank_data.items():
        results.append({"type": "bank_file", "id": filename, "content": content})
        
    dur = time.perf_counter() - start
    return results[:limit], dur

async def run_comparison(query: str):
    print(f"\n{'='*60}")
    print(f" COMPARISON QUERY: '{query}'")
    print(f"{'='*60}\n")

    # 1. LLM Re-ranking (Current implementation)
    print("Running: LLM Re-ranking (Current)...")
    start_llm = time.perf_counter()
    res_llm = await salvage_related_knowledge(query, session_id="comp_test")
    dur_llm = time.perf_counter() - start_llm
    
    print(f"  -> Duration: {dur_llm:.3f}s")
    print(f"  -> Results: {len(res_llm)} items")
    for i, item in enumerate(res_llm):
        # 軽量化プロンプトを使っているのでキーが 't' になっている可能性がある
        content = item.get("t") or item.get("content", "N/A")
        print(f"     [{i}] {str(content)[:100]}...")

    print("\n" + "-"*40 + "\n")

    # 2. Fast Path (No Re-ranking)
    print("Running: Fast Path (No Re-ranking)...")
    res_fast, dur_fast = await mock_perform_search_only(query, limit=5)
    
    print(f"  -> Duration: {dur_fast:.3f}s")
    print(f"  -> Results: {len(res_fast)} items")
    for i, item in enumerate(res_fast):
        print(f"     [{i}] {str(item['content'])[:100]}...")

    print(f"\n{'='*60}")
    print(f" SUMMARY")
    print(f"  LLM Path:  {dur_llm:.7f}s")
    print(f"  Fast Path: {dur_fast:.7f}s")
    speedup = dur_llm / dur_fast if dur_fast > 0 else 0
    print(f"  SPEEDUP:   {speedup:.1f}x faster")
    print(f"{'='*60}\n")

async def main():
    # DB初期化
    print(f"Initializing Databases...")
    await init_db()
    await init_thoughts_db()
    
    print(f"Main DB: {get_db_path()}")
    print(f"Thoughts DB: {get_thoughts_db_path()}")
    
    queries = [
        "ProjectX",
        "Explain the design pattern of the server",
        "Recent observations about entities"
    ]
    
    for q in queries:
        await run_comparison(q)

if __name__ == "__main__":
    asyncio.run(main())
