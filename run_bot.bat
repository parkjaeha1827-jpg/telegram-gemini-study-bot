@echo off
title Telegram Gemini Study Bot Runner
cd /d "%~dp0"
echo ===================================================
echo 🤖 Starting Telegram Study Bot (@agent123_ai_bot)...
echo ===================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Please run: python -m venv .venv
    pause
    exit /b 1
)

".venv\Scripts\python.exe" bot_polling.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Bot stopped with error code %ERRORLEVEL%.
)
pause
