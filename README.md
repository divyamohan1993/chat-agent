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
- 📊 **Deterministic Qualification**: Clear rules for lead qualification
- 💾 **Full Persistence**: SQLite database + conversation transcripts
- 🚀 **CPU-Optimized**: Runs entirely on CPU - no GPU required

## � Quick Start (One Command)

### Windows

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

**Access the demo at:** http://localhost:8000/demo

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

# Copy and configure environment
cp .env.example .env

# Start server
python main.py serve
```

## 📁 Project Structure

```
chat-agent/
├── run_project.bat        # One-click setup & run (Windows)
├── .env.example           # Environment configuration template
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
│   └── search_scout.py    # Property search scraper
├── frontend/              # Web UI
│   ├── index.html         # Demo page
│   └── widget.js          # Chat widget
├── data/                  # Persistence layer
│   ├── logs/              # Conversation transcripts
│   ├── leads/             # Lead summaries (JSON backup)
│   └── emails/            # Email queue/logs
├── prompts/               # AI prompt templates
├── docs/                  # Documentation
└── tests/                 # Test suite
```

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info and status |
| `/demo` | GET | Chat widget demo page |
| `/api/status` | GET | System component status |
| `/api/qualify` | POST | Trigger lead qualification |
| `/api/search` | GET | Search properties on realtyassistant.in |
| `/api/leads` | GET/POST | List or create leads |
| `/api/leads/{session_id}` | GET | Get specific lead details |
| `/api/transcripts/{id}` | GET | Get conversation transcript |
| `/api/send-summary-email` | POST | Send email summary |
| `/api/initiate-call` | POST | Initiate outbound voice call |

### Search Properties

```bash
curl "http://localhost:8000/api/search?location=Mumbai&property_type=residential&topology=2BHK"
```

## 🎯 Conversation Flow

1. **Greeting** - Welcome and introduction
2. **Location** - Collect preferred area
3. **Category** - Residential or Commercial
4. **Property Type** - Apartment, Villa, Plot, etc.
5. **Bedroom** - BHK configuration
6. **Possession** - Timeline preference
7. **Search** - Query realtyassistant.in and display results
8. **Consent** - Ask if user wants sales representative contact
9. **Contact Info** - Collect phone/email (if consent given)
10. **Closing** - Thank you and save lead

## ✅ Qualification Rules

A lead is **QUALIFIED** if:
- ✓ User consents to sales representative contact
- ✓ Valid contact information provided

Otherwise, the lead is **NOT QUALIFIED** (property search still shown).

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | - | Google Gemini API key (fallback) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `gemma3:1b` | Local LLM model |
| `LLM_TIMEOUT_SECONDS` | `3.5` | Fallback threshold |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |
| `SMTP_*` | - | Email configuration (optional) |

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

## 📞 Voice Integration (Optional)

Supports Twilio and VAPI.ai for outbound voice calls. See [docs/INTEGRATION_NOTES.md](docs/INTEGRATION_NOTES.md) for setup instructions.

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
└───────┼────────────┼────────────┼─────────────────┼──────────┘
        │            │            │                 │
        v            v            v                 v
   ┌────────┐  ┌──────────┐  ┌──────────┐    ┌──────────┐
   │ Audio  │  │ Ollama/  │  │ Realty   │    │  Local   │
   │ Input  │  │ Gemini   │  │ Assistant│    │  Storage │
   └────────┘  └──────────┘  └──────────┘    └──────────┘
```

## 📄 License

MIT License - see LICENSE file for details.

---

Built with ❤️ by [dmj.one](https://dmj.one)
