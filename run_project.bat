@echo off
echo ============================================================
echo   RealtyAssistant AI Agent - Auto Launcher
echo ============================================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

REM Create venv
if not exist "venv" (
    echo [1/5] Creating virtual environment...
    python -m venv venv
) else (
    echo [1/5] Virtual environment exists.
)

REM Activate venv
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo [3/5] Installing/Updating dependencies...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARNING] Standard install failed. Attempting fallback installation...
    pip install fastapi uvicorn python-dotenv rich pydantic
    pip install google-generativeai ollama httpx aiohttp
    pip install playwright beautifulsoup4 lxml
    pip install faster-whisper numpy scipy sounddevice
    pip install tenacity pydantic-settings python-multipart
)

REM Install Playwright
echo [4/5] Checking Playwright browsers...
playwright install chromium 2>nul
if errorlevel 1 (
     echo [INFO] Installing Playwright dependencies...
     playwright install --with-deps chromium
)

REM Ensure directories exist
if not exist "data\logs" mkdir "data\logs"
if not exist "data\leads" mkdir "data\leads"

REM Setup .env if missing
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo.
        echo [IMPORTANT] Created .env file from template.
        echo [IMPORTANT] Please edit .env and add your API keys before using AI features.
        echo.
    )
)

echo.
echo ============================================================
echo   Starting RealtyAssistant...
echo   Access the UI at: http://localhost:8000/demo
echo ============================================================
echo.

python main.py serve
pause
