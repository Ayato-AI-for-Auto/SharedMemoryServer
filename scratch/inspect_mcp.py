from fastmcp import FastMCP
import logging

mcp = FastMCP("test")
print(f"FastMCP attributes: {dir(mcp)}")

# Check if _app or similar exists
if hasattr(mcp, "_app"):
    print("_app found")
else:
    print("_app NOT found")

# Try to find where the starlette app lives
try:
    from fastmcp.server.fastapi import FastAPIServer
    print("FastAPIServer found in imports")
except ImportError:
    print("FastAPIServer NOT found in imports")
