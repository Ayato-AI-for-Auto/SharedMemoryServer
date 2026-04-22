import asyncio
import os
import sqlite3
from shared_memory.thought_logic import process_thought_core
from shared_memory.database import init_db, async_get_connection
from shared_memory.utils import get_logger

logger = get_logger("verification")

async def verify_synergy():
    print("\n=== PHASE 1: INITIALIZATION ===")
    await init_db()
    
    session_id = "verification_session_synergy"
    
    # 0. Setup Initial Knowledge via logic to ensure embeddings are generated
    from shared_memory.logic import save_memory_core
    await save_memory_core(
        entities=[{
            "name": "Project Phoenix",
            "entity_type": "Project",
            "description": "A top-secret project developing anti-gravity tech."
        }],
        agent_id="setup_script"
    )
    print("Initial knowledge setup complete (with embeddings).")

    print("\n=== PHASE 2: THOUGHT STEP 1 (SALVAGE TEST) ===")
    # Agent thinks about Project Phoenix - should salvage the anti-gravity fact
    res1 = await process_thought_core(
        thought="I need to check the status of Project Phoenix and its core technology.",
        thought_number=1,
        total_thoughts=3,
        next_thought_needed=True,
        session_id=session_id
    )
    
    print(f"Step 1 related knowledge count: {len(res1.get('related_knowledge', []))}")
    for item in res1.get('related_knowledge', []):
        print(f" - Salvaged [{item['type']}]: {item['id']} -> {item['content'][:100]}")

    print("\n=== PHASE 3: THOUGHT STEP 2 (ACCRETION TEST) ===")
    # Agent discovers a new fact - should be saved via Accretion
    await process_thought_core(
        thought="I found that Project Phoenix uses a 'Graviton Reactor' located in Sector 7.",
        thought_number=2,
        total_thoughts=3,
        next_thought_needed=True,
        session_id=session_id
    )
    
    # Wait for background task to finish
    print("Waiting for background accretion task...")
    await asyncio.sleep(5) 

    # Check if 'Graviton Reactor' exists in DB
    async with await async_get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM entities WHERE name LIKE '%Graviton Reactor%'")
        row = await cursor.fetchone()
        if row:
            print(f"SUCCESS: Accretion captured new entity: {row[0]} ({row[2]})")
        else:
            # Check observations as well
            cursor = await conn.execute("SELECT * FROM observations WHERE content LIKE '%Sector 7%'")
            row = await cursor.fetchone()
            if row:
                print(f"SUCCESS: Accretion captured new observation: {row[2]}")
            else:
                print("FAILURE: Accretion did not capture new knowledge.")

    print("\n=== PHASE 4: FINAL WRAP-UP ===")
    await process_thought_core(
        thought="Finalizing my review of Project Phoenix and Sector 7.",
        thought_number=3,
        total_thoughts=3,
        next_thought_needed=False,
        session_id=session_id
    )
    print("Verification complete.")

if __name__ == "__main__":
    asyncio.run(verify_synergy())
