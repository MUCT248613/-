@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
title VirtualStudent Sandbox - Stop

rem ============================================================
rem  VirtualStudent Sandbox v5.0 - stop both services
rem  Kills the backend supervisor (which auto-restarts uvicorn),
rem  any uvicorn worker, and the frontend vite dev server.
rem  Logic lives in scripts\kill_services.ps1.
rem ============================================================

set "ROOT=%~dp0"

echo.
taskkill /FI "WINDOWTITLE eq VS Backend (6668)" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq VS Frontend (4000)" /T /F >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\kill_services.ps1"

echo.
echo Backend (6668) and frontend (4000) have been stopped.
echo.

endlocal
timeout /t 3 >nul
