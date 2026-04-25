@echo off
pushd "%~dp0.."
echo Starting SharedMemoryServer (SSE on Port 8377)...
uv run shared-memory --sse --port 8377
popd
