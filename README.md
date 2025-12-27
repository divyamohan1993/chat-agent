# RealtyAssistant AI Agent

> AI-powered Voice/Chat Agent for Real Estate Lead Qualification

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🏠 Overview

RealtyAssistant AI Agent is a production-ready system that qualifies real estate leads through voice or chat interactions. It follows a scripted conversation flow to collect property requirements, checks availability on [realtyassistant.in](https://realtyassistant.in), and makes qualification decisions.

### Key Features

- 🎙️ **Voice & Chat Support**: Handle leads via voice calls or text chat
- 🤖 **Hybrid LLM Architecture**: Local Ollama inference with Gemini fallback
- 🔍 **Live Property Search**: Real-time scraping of realtyassistant.in
- 🎯 **Accent Handling**: Robust fuzzy matching for Indian English accents
- 📊 **Deterministic Qualification**: Clear rules for lead qualification
- 💾 **Full Persistence**: SQLite database + conversation transcripts
- 🚀 **CPU-Optimized**: Runs entirely on CPU - no GPU required

## 🚀 Quick Start (One Command)

### Windows (Development)

```batch
run_project.bat
```

This single script will:
1. ✅ Check Python installation
2. ✅ Create/verify virtual environment
3. ✅ Install all dependencies
4. ✅ Setup Playwright browsers
5. ✅ Create required directories
6. ✅ Check if port is available (with auto-kill option)
7. ✅ Start the server

**Access the demo at:** http://localhost:20000/demo

### Linux/Ubuntu VM (Production)

```bash
sudo bash run_project.sh
```

This script will:
1. ✅ Install Python, pip, and nginx
2. ✅ Create virtual environment and install dependencies
3. ✅ Setup Playwright browsers
4. ✅ Create systemd service for auto-start
5. ✅ Configure nginx for reverse proxy
6. ✅ Start all services

**Production Access:** https://reas.dmj.one/task1/demo

## 🌐 Production Deployment

### One-Click VM Deployment

For a blank Ubuntu VM, simply clone and run:

```bash
# Clone the repository
git clone https://github.com/divyamohan1993/chat-agent.git
cd chat-agent

# Run the deployment script (does EVERYTHING)
sudo bash run_project.sh
```

### What Gets Deployed

| Component | Details |
|-----------|---------|
| **App Service** | systemd service `realtyassistant.service` |
| **Internal Port** | 20000 (localhost only) |
| **Nginx Proxy** | Serves at `/task1/` path |
| **Domain** | `reas.dmj.one` |
| **Public URLs** | `/task1/demo`, `/task1/voice`, `/task1/api/*` |

### DNS Configuration

Point your domain's A record to the VM IP:
```
reas.dmj.one → <VM_IP_ADDRESS>
```

### Management Commands

```bash
# View application logs
sudo journalctl -u realtyassistant -f

# Restart the application
sudo systemctl restart realtyassistant

# Stop the application
sudo systemctl stop realtyassistant

# Restart nginx
sudo systemctl restart nginx

# Check service status
sudo systemctl status realtyassistant
```

### Manual Setup (Any OS)

```bash
# Clone repository
git clone https://github.com/divyamohan1993/chat-agent.git
cd chat-agent

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Configure environment
# Edit .env with your GEMINI_API_KEY

# Start server
python main.py serve
```

## 📁 Project Structure

```
chat-agent/
├── run_project.bat        # One-click setup & run (Windows)
├── .env                   # Environment configuration
├── main.py                # FastAPI server & CLI entry point
├── agent.py               # Main qualification agent logic
├── models.py              # Pydantic data models
├── requirements.txt       # Python dependencies
├── core/                  # Core engine modules
│   ├── __init__.py
│   ├── database.py        # SQLite lead storage
│   ├── whisper_engine.py  # Local STT with faster-whisper
│   ├── llm_engine.py      # Hybrid LLM (Ollama + Gemini)
│   ├── fallback.py        # Gemini API fallback
│   ├── search_scout.py    # Property search scraper
│   └── voice_handler.py   # Voice call handler with accent support
├── frontend/              # Web UI
│   ├── index.html         # Demo page
│   ├── widget.js          # Chat widget
│   └── voice.html         # Voice testing page
├── data/                  # Persistence layer
│   ├── logs/              # Conversation transcripts
│   ├── leads/             # Lead summaries (JSON backup)
│   └── leads.db           # SQLite database
└── tests/                 # Test suite
```

## 📡 API Endpoints

### Chat & Property Search

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info and status |
| `/demo` | GET | Chat widget demo page |
| `/voice` | GET | Voice testing page |
| `/api/status` | GET | System component status |
| `/api/search` | GET | Search properties on realtyassistant.in |
| `/api/qualify` | POST | Trigger lead qualification |
| `/api/leads` | GET/POST | List or create leads |
| `/api/leads/{session_id}` | GET | Get specific lead details |

### Voice API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/voice/start` | POST | Start a new voice session |
| `/api/voice/process` | POST | Process speech input |
| `/api/voice/session/{id}` | GET | Get session state |
| `/api/voice/session/{id}` | DELETE | End voice session |
| `/webhooks/twilio/voice-ai` | POST | Enhanced Twilio voice webhook |
| `/webhooks/twilio/process-ai` | POST | Process Twilio speech with AI |

### Search Properties Example

```bash
curl "http://localhost:8080/api/search?location=Noida&property_type=residential&topology=2BHK"
```

## 🎯 Conversation Flow

1. **Greeting** - Welcome and introduction
2. **Location** - Collect preferred area (with accent handling)
3. **Category** - Residential or Commercial
4. **Property Type** - Apartment, Villa, Plot, etc.
5. **Bedroom** - BHK configuration
6. **Search** - Query realtyassistant.in and display results
7. **Consent** - Ask if user wants sales representative contact
8. **Contact Info** - Collect budget, phone, email (if consent given)
9. **Closing** - Thank you and save lead

## 🎤 Voice Accent Handling

The voice handler includes robust fuzzy matching for:

| Spoken | Understood |
|--------|------------|
| "Noyda", "Noeda" | Noida |
| "Gurgaon", "Gurugaon" | Gurugram |
| "Bombay", "Bambai" | Mumbai |
| "Dilli", "Dehli" | Delhi |
| "Banaras", "Benares" | Varanasi |
| "Two BHK", "Do BHK" | 2 BHK |
| "Haan", "Ji", "Thik hai" | Yes (consent) |
| "Nahi", "Na" | No (consent) |

## ✅ Qualification Rules

A lead is **QUALIFIED** if:
- ✓ User consents to sales representative contact
- ✓ Valid contact information provided

Otherwise, the lead is **NOT QUALIFIED** (property search still shown).

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | - | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.0-flash-exp` | Gemini model to use |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `gemma3:1b` | Local LLM model |
| `LLM_TIMEOUT_SECONDS` | `3.5` | Fallback threshold |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8080` | Server port |
| `SMTP_*` | - | Email configuration (optional) |

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

## 📞 Voice Integration

### Browser-based (Demo)
1. Go to http://localhost:8080/voice
2. Click the microphone to start a session
3. Speak naturally (accent variations supported)
4. The bot responds via text-to-speech

### Twilio (Production)
Configure your Twilio webhook URL to:
```
https://your-domain.com/webhooks/twilio/voice-ai
```

Supports:
- Indian English voice (Polly.Aditi)
- Speech hints for better recognition
- Automatic lead saving

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Server                          │
├─────────────────────────────────────────────────────────────┤
│                    Qualification Agent                       │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │
│  │ Whisper │  │  LLM    │  │ Property│  │   Database      │ │
│  │ (STT)   │  │ Engine  │  │ Searcher│  │   (SQLite)      │ │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────────┬────────┘ │
│       │            │            │                 │          │
│  ┌────┴────────────┴────────────┴─────────────────┴────────┐ │
│  │                    Voice Handler                         │ │
│  │  - Fuzzy Matching for Accents                           │ │
│  │  - Session Management                                    │ │
│  │  - Twilio/Browser Integration                           │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
        │            │            │                 │
        v            v            v                 v
   ┌────────┐  ┌──────────┐  ┌──────────┐    ┌──────────┐
   │ Audio  │  │ Gemini/  │  │ Realty   │    │  SQLite  │
   │ Input  │  │ Ollama   │  │ Assistant│    │  Storage │
   └────────┘  └──────────┘  └──────────┘    └──────────┘
```

## 📄 License

MIT License - see LICENSE file for details.

---

Built with ❤️ by [dmj.one](https://dmj.one)
