@echo off
pushd "%~dp0.."
echo Registering SharedMemoryServer with IDEs...
uv run shared-memory-register
pause
popd
