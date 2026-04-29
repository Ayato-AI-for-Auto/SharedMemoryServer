import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    async with sse_client("http://127.0.0.1:8377/sse") as (read, write):
        async with ClientSession(read, write) as session:
            print("Connecting and initializing...")
            await session.initialize()
            print("Initialization successful!")
            
            print("Calling read_memory...")
            result = await session.call_tool("read_memory", arguments={"query": "test"})
            print(f"Result: {result}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Verification failed: {e}")
