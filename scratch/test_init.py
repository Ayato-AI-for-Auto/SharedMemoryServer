import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from shared_memory.database import init_db
from shared_memory import thought_logic

async def test_init():
    print("Testing init_db()...")
    try:
        await init_db()
        print("init_db() success!")
    except Exception as e:
        print(f"init_db() failed: {e}")
        return

    print("Testing init_thoughts_db()...")
    try:
        await thought_logic.init_thoughts_db()
        print("init_thoughts_db() success!")
    except Exception as e:
        print(f"init_thoughts_db() failed: {e}")
        return

    print("All initializations complete!")

if __name__ == "__main__":
    asyncio.run(test_init())
