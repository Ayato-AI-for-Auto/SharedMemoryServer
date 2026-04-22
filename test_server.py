import sys
import json
from fastmcp import FastMCP

mcp = FastMCP("TestServer")

@mcp.tool()
def hello(name: str = "World") -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()
