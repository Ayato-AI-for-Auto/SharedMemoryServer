@echo off
pushd "%~dp0.."
echo Starting SharedMemoryServer (STDIO)...
uv run shared-memory
popd
