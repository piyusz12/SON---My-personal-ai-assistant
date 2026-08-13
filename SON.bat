@echo off
title SON V3 - Holographic Personal AI Assistant
cd /d "C:\AI\SON"

echo =================================================================
echo             STARTING SON V3 HOLOGRAPHIC ASSISTANT
echo =================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launch_son.py %*
) else (
    python launch_son.py %*
)

pause
