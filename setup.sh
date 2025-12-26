#!/bin/bash
# =============================================================================
# RealtyAssistant AI Agent - Linux/Mac Setup Script
# =============================================================================
# This script sets up the virtual environment and installs all dependencies
# for CPU-only execution.

echo ""
echo "============================================================"
echo "  RealtyAssistant AI Agent - Setup Script"
echo "============================================================"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed."
    echo "Please install Python 3.10+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# Create virtual environment
echo "[1/5] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "      Virtual environment created."
else
    echo "      Virtual environment already exists."
fi

# Activate virtual environment
echo "[2/5] Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "[3/5] Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "[4/5] Installing dependencies (this may take a few minutes)..."
pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "[WARNING] Some packages failed. Trying individual install..."
    pip install fastapi uvicorn python-dotenv rich pydantic
    pip install google-generativeai ollama httpx aiohttp
    pip install playwright beautifulsoup4 lxml
    pip install faster-whisper numpy scipy sounddevice
    pip install tenacity pydantic-settings python-multipart
    pip install pytest pytest-asyncio
fi

# Install Playwright browsers
echo "[5/5] Installing Playwright browsers..."
playwright install chromium --with-deps 2>/dev/null || {
    echo "[WARNING] Playwright browser install failed. Run manually:"
    echo "         playwright install chromium"
}

# Create data directories
mkdir -p data/logs
mkdir -p data/leads

# Copy .env if not exists
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo ""
        echo "[IMPORTANT] Created .env file from template."
        echo "Please edit .env and add your API keys."
    fi
fi

echo ""
echo "============================================================"
echo "  Setup Complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env file with your API keys"
echo "  2. (Optional) Install Ollama from https://ollama.ai/"
echo "  3. Run: python main.py serve"
echo ""
echo "Or start directly:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
