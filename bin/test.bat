@echo off
pushd "%~dp0.."
echo Running SharedMemoryServer Test Suite...
uv run pytest tests -v
pause
popd
