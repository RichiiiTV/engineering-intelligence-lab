@echo off
setlocal
cd /d "%~dp0.."
if not defined UV_CACHE_DIR set "UV_CACHE_DIR=%CD%\.uv-cache"
if "%~1"=="--skip-build" goto serve
pushd frontend
if exist node_modules goto build
call npm.cmd ci
if errorlevel 1 goto frontend_failed
:build
call npm.cmd run build
if errorlevel 1 goto frontend_failed
popd
:serve
echo Workbench: http://127.0.0.1:8000/  (Ctrl+C to stop)
uv run --locked --extra documents uvicorn eil.api:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 5
exit /b %ERRORLEVEL%
:frontend_failed
echo Frontend setup failed.
popd
exit /b 1
