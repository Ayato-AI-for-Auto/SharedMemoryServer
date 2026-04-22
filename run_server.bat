@echo off
set MEMORY_DB_PATH=C:\Users\saiha\My_Service\programing\MCP\SharedMemoryServer\shared_memory.db
set MEMORY_BANK_DIR=C:\Users\saiha\My_Service\programing\MCP\SharedMemoryServer\memory-bank
set PYTHONPATH=C:\Users\saiha\My_Service\programing\MCP\SharedMemoryServer;C:\Users\saiha\My_Service\programing\MCP\SharedMemoryServer\src
C:\Users\saiha\My_Service\programing\MCP\SharedMemoryServer\.venv\Scripts\python.exe C:\Users\saiha\My_Service\programing\MCP\SharedMemoryServer\src\shared_memory\server.py %*
