@echo off
title Legend Discord Bot
echo Starting Legend Discord Bot...

if not exist .venv\Scripts\python.exe (
    echo Error: Virtual environment not found. Please set up .venv first.
    pause
    exit /b 1
)

if not exist .env (
    echo Error: .env file not found. Copying .env.example to .env...
    copy .env.example .env
    echo Please edit .env with your Discord Bot Token and YouTube API key.
    pause
    exit /b 1
)

.venv\Scripts\python.exe src\main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Bot stopped with an error. Check logs\bot.log for details.
    pause
)

