@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
title VirtualStudent Sandbox - Launcher

rem ============================================================
rem  VirtualStudent Sandbox v6.0 - one-click launcher
rem  Backend  : FastAPI / uvicorn  ->  http://localhost:6668
rem  Frontend : Vite dev server    ->  http://localhost:4000
rem
rem  Double-click this file. Two console windows open:
rem    - "VS Backend (6668)"   runs uvicorn with auto-restart
rem    - "VS Frontend (4000)"  runs the Vite dev server
rem  Close a window (or Ctrl+C in it) to stop that service,
rem  or run stop.bat to stop both at once.
rem ============================================================

set "ROOT=%~dp0"
cd /d "%ROOT%"

rem Prefer the project-local backend environment when it exists. This keeps
rem the launcher aligned with the interpreter used to verify the API and
rem avoids silently starting a different Python installation without FastAPI.
if exist "%ROOT%.backend-venv\Scripts\python.exe" (
    set "BACKEND_PY=%ROOT%.backend-venv\Scripts\python.exe"
) else (
    set "BACKEND_PY=python"
)

if not exist logs mkdir logs

echo.
echo ============================================================
echo   VirtualStudent Sandbox v6.0
echo ============================================================
echo.

rem ---- Pre-launch cleanup: kill any previous backend/frontend instances ----
rem  Terminates the backend SUPERVISOR (which auto-restarts uvicorn) plus any
rem  process still listening on 6668 / 4000, so uvicorn never fails with
rem  "port already in use" (winerror 10048). See scripts\kill_services.ps1.
echo [launcher] stopping any previously running services ...
taskkill /FI "WINDOWTITLE eq VS Backend (6668)" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq VS Frontend (4000)" /T /F >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\kill_services.ps1"
rem give the OS a moment to release the sockets
timeout /t 2 /nobreak >nul
echo.

rem ---- Frontend dependencies (install once if missing) ----
if not exist "%ROOT%frontend\node_modules" (
    echo [launcher] frontend dependencies missing, running "npm install" ...
    pushd "%ROOT%frontend"
    call npm install
    popd
    echo.
)

rem ---- Backend dependencies (install once if missing) ----
rem  The API import chain needs fastapi/uvicorn/pydantic/numpy/scipy/networkx/
rem  duckdb/yaml. If any is absent (e.g. a fresh machine), install exactly the
rem  missing ones so the backend window doesn't die with ModuleNotFoundError.
set "MISSING_DEPS="
for /f "usebackq delims=" %%m in (`"%BACKEND_PY%" "%ROOT%scripts\check_backend_deps.py"`) do set "MISSING_DEPS=%%m"
if defined MISSING_DEPS (
    echo [launcher] backend dependencies missing: %MISSING_DEPS%
    echo [launcher] running "pip install %MISSING_DEPS%" ...
    pip install %MISSING_DEPS%
    echo.
)

rem ---- Backend: uvicorn + auto-restart supervisor ----
echo [launcher] starting backend   -^>  http://localhost:6668
start "VS Backend (6668)" /D "%ROOT%" cmd /k "%BACKEND_PY%" scripts\supervise_backend.py

rem ---- Frontend: Vite dev server (proxies /api to 6668) ----
echo [launcher] starting frontend  -^>  http://localhost:4000
start "VS Frontend (4000)" /D "%ROOT%frontend" cmd /k npm run dev

echo.
echo ============================================================
echo   Both services are starting in separate windows.
echo.
echo     Backend  :  http://localhost:6668   (window: VS Backend)
echo     Frontend :  http://localhost:4000   (window: VS Frontend)
echo.
echo   Open  http://localhost:4000  in your browser.
echo   Remember to set your Bailian API key on the Settings page.
echo ============================================================
echo.

endlocal
timeout /t 8 >nul
