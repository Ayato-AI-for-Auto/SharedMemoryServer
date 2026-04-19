import asyncio
import inspect

from google import genai


async def main():
    client = genai.Client(api_key="EMPTY")
    # Check embed_content
    is_coro = inspect.iscoroutinefunction(client.aio.models.embed_content)
    print(f"embed_content is coroutine: {is_coro}")
    # Check generate_content
    is_gen_coro = inspect.iscoroutinefunction(client.aio.models.generate_content)
    print(f"generate_content is coroutine: {is_gen_coro}")

    # Check list
    print("list return type check...")
    try:
        res = client.aio.models.list()
        print(f"list returns: {type(res)}")
        # Check if it has __aiter__
        print(f"is async iterable: {hasattr(res, '__aiter__')}")
    except Exception as e:
        print(f"Error checking list: {e}")


if __name__ == "__main__":
    asyncio.run(main())
