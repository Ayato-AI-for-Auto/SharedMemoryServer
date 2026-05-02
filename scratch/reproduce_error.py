
import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.abspath("src"))

from shared_memory.core.thought_logic import process_thought_core, init_thoughts_db
from shared_memory.infra.database import init_db

async def reproduce():
    print("Initializing databases...")
    await init_db()
    await init_thoughts_db(force=True)
    
    print("Attempting to process thought with session_id=None...")
    try:
        result = await process_thought_core(
            thought="This should fail if session_id is None.",
            thought_number=1,
            total_thoughts=1,
            next_thought_needed=False,
            session_id=None
        )
        print("Success? (This was unexpected):", result)
    except Exception as e:
        print(f"Caught expected error: {e}")

if __name__ == "__main__":
    asyncio.run(reproduce())
