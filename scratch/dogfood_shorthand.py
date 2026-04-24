import asyncio
import logging
from mcp import ClientSession
from mcp.client.sse import sse_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dogfood-shorthand")

async def run_dogfood():
    server_url = "http://127.0.0.1:8377/sse"
    logger.info(f"Connecting to SharedMemoryServer to test SHORTHAND input...")
    
    try:
        async with sse_client(server_url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # Test Shorthand: Using strings instead of dicts
                logger.info("Step 1: Saving memory using string SHORTHANDS...")
                save_result = await session.call_tool("save_memory", {
                    "entities": ["ShorthandNode"],
                    "observations": ["This observation was sent as a simple string."]
                })
                
                if save_result.isError:
                    logger.error(f"FAILURE: save_memory still fails: {save_result.content}")
                    return
                
                logger.info(f"Save Result: {save_result.content[0].text}")
                
                # Verify retrieval
                logger.info("Step 2: Verifying retrieval of shorthand data...")
                read_result = await session.call_tool("read_memory", {"query": "ShorthandNode"})
                if "ShorthandNode" in read_result.content[0].text:
                    logger.info("SUCCESS: Shorthand data correctly saved and retrieved!")
                else:
                    logger.error("FAILURE: Shorthand data NOT found.")

                logger.info("Shorthand flexibility test COMPLETED SUCCESSFULY.")

    except Exception as e:
        logger.error(f"Error during dogfooding: {e}")

if __name__ == "__main__":
    asyncio.run(run_dogfood())
