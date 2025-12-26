@echo off
REM =============================================================================
REM RealtyAssistant AI Agent - Windows Setup Script
REM =============================================================================
REM This script sets up the virtual environment and installs all dependencies
REM for CPU-only execution.

echo.
echo ============================================================
echo   RealtyAssistant AI Agent - Setup Script
echo ============================================================
echo.

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

REM Create virtual environment
echo [1/5] Creating virtual environment...
if not exist "venv" (
    python -m venv venv
    echo      Virtual environment created.
) else (
    echo      Virtual environment already exists.
)

REM Activate virtual environment
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo [3/5] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install dependencies
echo [4/5] Installing dependencies (this may take a few minutes)...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARNING] Some packages failed. Trying individual install...
    pip install fastapi uvicorn python-dotenv rich pydantic
    pip install google-generativeai ollama httpx aiohttp
    pip install playwright beautifulsoup4 lxml
    pip install faster-whisper numpy scipy sounddevice
    pip install tenacity pydantic-settings python-multipart
    pip install pytest pytest-asyncio
)

REM Install Playwright browsers
echo [5/5] Installing Playwright browsers...
playwright install chromium --with-deps 2>nul
if errorlevel 1 (
    echo [WARNING] Playwright browser install failed. Run manually:
    echo          playwright install chromium
)

REM Create data directories
if not exist "data\logs" mkdir "data\logs"
if not exist "data\leads" mkdir "data\leads"

REM Copy .env if not exists
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo.
        echo [IMPORTANT] Created .env file from template.
        echo Please edit .env and add your API keys.
    )
)

echo.
echo ============================================================
echo   Setup Complete!
echo ============================================================
echo.
echo Next steps:
echo   1. Edit .env file with your API keys
echo   2. (Optional) Install Ollama from https://ollama.ai/
echo   3. Run: python main.py serve
echo.
echo Or start directly:
echo   venv\Scripts\activate
echo   python main.py
echo.

pause
