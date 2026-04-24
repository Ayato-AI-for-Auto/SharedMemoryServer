@echo off
pushd "%~dp0.."
echo Starting SharedMemoryServer Admin Dashboard...
uv run shared-memory-admin-server
popd
