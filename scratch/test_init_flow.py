import asyncio
import os
import sys
from loguru import logger

# Add src to sys.path
sys.path.append(os.path.join(os.getcwd(), "src"))

async def test_initialization_flow():
    """
    Simulates the server's background initialization flow to verify
    database connections, migrations, and error handling.
    """
    logger.info("Starting Initialization Flow Test...")
    
    # 1. Setup temporary environment for testing
    import tempfile
    test_dir = tempfile.mkdtemp(prefix="init_test_")
    os.environ["SHARED_MEMORY_HOME"] = test_dir
    logger.info(f"Using temporary test directory: {test_dir}")

    try:
        # 2. Import core components
        from shared_memory.infra.database import init_db
        from shared_memory.core import thought_logic
        
        # 3. Test Step 1: Main DB
        logger.info("Executing Step 1: Main Database Init...")
        await init_db(force=True)
        logger.info("Step 1 PASSED.")

        # 4. Test Step 2: Thoughts DB
        logger.info("Executing Step 2: Thoughts Database Init...")
        await thought_logic.init_thoughts_db(force=True)
        logger.info("Step 2 PASSED.")

        # 5. Verify files exist
        db_path = os.path.join(test_dir, "knowledge.db")
        thoughts_path = os.path.join(test_dir, "thoughts.db")
        
        if os.path.exists(db_path) and os.path.exists(thoughts_path):
            logger.info(f"SUCCESS: Database files created at {test_dir}")
        else:
            raise RuntimeError("Database files were not created!")

        logger.info("=== INITIALIZATION FLOW TEST COMPLETED SUCCESSFULLY ===")

    except Exception as e:
        logger.error(f"!!! INITIALIZATION FLOW TEST FAILED: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        import shutil
        try:
            from shared_memory.infra.database import close_all_connections
            await close_all_connections()
            shutil.rmtree(test_dir, ignore_errors=True)
            logger.info("Cleanup completed.")
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_initialization_flow())
