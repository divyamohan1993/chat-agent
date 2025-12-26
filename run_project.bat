@echo off
setlocal EnableDelayedExpansion

:: ============================================================
:: RealtyAssistant AI Agent - One-Click Setup & Run
:: ============================================================
:: This script is IDEMPOTENT - safe to run multiple times.
:: It will install, configure, and run on a blank Windows server.
:: ============================================================

echo.
echo ============================================================
echo   RealtyAssistant AI Agent - One-Click Setup ^& Run
echo ============================================================
echo.

:: Configuration
set PORT=8000
set PYTHON_MIN_VERSION=3.10

:: ============================================================
:: STEP 1: Check Python Installation
:: ============================================================
echo [1/7] Checking Python installation...

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [ERROR] Python is not installed or not in PATH.
    echo   Please install Python %PYTHON_MIN_VERSION%+ from https://www.python.org/
    echo   Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Get Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo   Python %PYTHON_VERSION% found.

:: ============================================================
:: STEP 2: Create/Verify Virtual Environment
:: ============================================================
echo [2/7] Setting up virtual environment...

if not exist "venv\Scripts\activate.bat" (
    echo   Creating new virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo   [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo   Virtual environment created.
) else (
    echo   Virtual environment already exists.
)

:: ============================================================
:: STEP 3: Activate Virtual Environment
:: ============================================================
echo [3/7] Activating virtual environment...
call venv\Scripts\activate.bat

:: ============================================================
:: STEP 4: Install/Update Dependencies
:: ============================================================
echo [4/7] Installing/Updating dependencies...

:: Upgrade pip silently
python -m pip install --upgrade pip --quiet 2>nul

:: Install from requirements.txt
if exist "requirements.txt" (
    pip install -r requirements.txt --quiet 2>nul
    if errorlevel 1 (
        echo   [WARNING] Some packages may have failed. Installing core packages...
        pip install fastapi uvicorn python-dotenv rich pydantic --quiet 2>nul
        pip install google-generativeai ollama httpx aiohttp --quiet 2>nul
        pip install playwright beautifulsoup4 lxml --quiet 2>nul
        pip install tenacity pydantic-settings python-multipart sqlalchemy --quiet 2>nul
    )
) else (
    echo   [WARNING] requirements.txt not found. Installing core packages...
    pip install fastapi uvicorn python-dotenv rich pydantic --quiet 2>nul
    pip install google-generativeai ollama httpx aiohttp --quiet 2>nul
    pip install playwright beautifulsoup4 lxml --quiet 2>nul
    pip install tenacity pydantic-settings python-multipart sqlalchemy --quiet 2>nul
)
echo   Dependencies installed.

:: ============================================================
:: STEP 5: Install Playwright Browsers (Idempotent)
:: ============================================================
echo [5/7] Setting up Playwright browsers...

:: Check if Playwright is already installed by testing import
python -c "from playwright.sync_api import sync_playwright" 2>nul
if errorlevel 1 (
    echo   Installing Playwright...
    pip install playwright --quiet 2>nul
)

:: Install Chromium browser (idempotent - skips if already installed)
playwright install chromium 2>nul
if errorlevel 1 (
    echo   Installing Playwright with system dependencies...
    playwright install --with-deps chromium 2>nul
)
echo   Playwright ready.

:: ============================================================
:: STEP 6: Create Required Directories & Config
:: ============================================================
echo [6/7] Setting up directories and configuration...

:: Create directories (idempotent)
if not exist "data" mkdir "data"
if not exist "data\logs" mkdir "data\logs"
if not exist "data\leads" mkdir "data\leads"
if not exist "data\emails" mkdir "data\emails"

:: Create .env from template if missing (idempotent)
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo   Created .env from template.
        echo.
        echo   ============================================================
        echo   [IMPORTANT] Please edit .env and add your API keys:
        echo     - GEMINI_API_KEY for AI fallback
        echo     - SMTP credentials for email (optional)
        echo   ============================================================
        echo.
    ) else (
        :: Create minimal .env
        (
            echo # RealtyAssistant Configuration
            echo OLLAMA_BASE_URL=http://localhost:11434
            echo OLLAMA_MODEL=gemma3:1b
            echo LLM_TIMEOUT_SECONDS=3.5
            echo ENABLE_GEMINI_FALLBACK=true
            echo LOGS_DIR=data/logs
            echo LEADS_DIR=data/leads
        ) > .env
        echo   Created minimal .env configuration.
    )
) else (
    echo   Configuration file exists.
)

:: ============================================================
:: STEP 7: Check Port & Start Server
:: ============================================================
echo [7/7] Checking port %PORT% and starting server...

:: Find PID using the port
set "PID_FOUND="
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    if not defined PID_FOUND set "PID_FOUND=%%a"
)

if defined PID_FOUND (
    echo.
    echo   ============================================================
    echo   [WARNING] Port %PORT% is already in use!
    echo   Process ID: !PID_FOUND!
    echo   ============================================================
    echo.
    
    :: Check if it's our own Python process
    for /f "tokens=1" %%n in ('tasklist /FI "PID eq !PID_FOUND!" /NH 2^>nul ^| findstr /i "python"') do (
        echo   The process appears to be Python - likely a previous instance.
    )
    
    echo.
    choice /C YN /M "   Kill process !PID_FOUND! and restart server"
    if !ERRORLEVEL! EQU 1 (
        echo.
        echo   Stopping process !PID_FOUND!...
        taskkill /PID !PID_FOUND! /F >nul 2>&1
        timeout /t 2 /nobreak >nul
        echo   Process stopped.
    ) else (
        echo.
        echo   Server start cancelled.
        echo   Please stop the process using port %PORT% and run this script again.
        pause
        exit /b 0
    )
) else (
    echo   Port %PORT% is available.
)

:: ============================================================
:: START SERVER
:: ============================================================
echo.
echo ============================================================
echo   RealtyAssistant AI Agent Starting...
echo   ------------------------------------------------------------
echo   Web UI:    http://localhost:%PORT%/demo
echo   API:       http://localhost:%PORT%/
echo   Status:    http://localhost:%PORT%/api/status
echo   ------------------------------------------------------------
echo   Press Ctrl+C to stop the server
echo ============================================================
echo.

:: Start the main application
python main.py serve

:: If we get here, server stopped
echo.
echo Server stopped.
pause
