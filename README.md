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
- 💾 **Full Persistence**: Conversation transcripts and JSON summaries
- 🚀 **CPU-Optimized**: Runs entirely on CPU - no GPU required

## 📁 Project Structure

```
realty-agent-onboard/
├── .env.example           # Environment configuration template
├── main.py                # FastAPI server & CLI entry point
├── agent.py               # Main qualification agent logic
├── models.py              # Pydantic data models
├── requirements.txt       # Python dependencies
├── core/                  # Core engine modules
│   ├── __init__.py
│   ├── whisper_engine.py  # Local STT with faster-whisper
│   ├── llm_engine.py      # Hybrid LLM (Ollama + Gemini)
│   ├── fallback.py        # Gemini API fallback
│   └── search_scout.py    # Property search scraper
├── data/                  # Persistence layer
│   ├── logs/              # Conversation transcripts
│   └── leads/             # Qualification summaries (JSON)
├── prompts/               # AI prompt templates
│   ├── system_prompt.md   # System instructions
│   └── conversation_templates.json
├── docs/                  # Documentation
│   └── INTEGRATION_NOTES.md
└── tests/                 # Test suite
    └── test_agent.py
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai/) (optional, for local LLM)
- Google Gemini API key (for fallback)

### Installation

1. **Clone and setup virtual environment**

```bash
cd realty-agent-onboard

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

2. **Install dependencies**

```bash
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

3. **Configure environment**

```bash
# Copy example config
copy .env.example .env

# Edit .env with your API keys
notepad .env
```

4. **Setup local LLM (optional)**

```bash
# Install Ollama from https://ollama.ai/
# Then pull the model
ollama pull llama3.1:8b
```

### Running the Agent

**Start the API server:**
```bash
python main.py serve
```

**Interactive CLI mode:**
```bash
python main.py cli
```

**Run simulation:**
```bash
python main.py simulate --name "John Doe" --phone "9876543210"
```

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info and status |
| `/api/status` | GET | System component status |
| `/api/qualify` | POST | Trigger lead qualification |
| `/api/search` | GET | Search properties on realtyassistant.in |
| `/api/leads` | GET | List all lead summaries |
| `/api/leads/{id}` | GET | Get specific lead details |
| `/api/transcripts/{id}` | GET | Get conversation transcript |
| `/api/initiate-call` | POST | Initiate outbound voice call (Twilio/VAPI) |
| `/demo` | GET | Chat widget demo page |
| `/webhooks/twilio/voice` | POST | Twilio voice webhook (TwiML) |
| `/webhooks/vapi/call` | POST | VAPI.ai webhook |

### Qualify a Lead

```bash
curl -X POST http://localhost:8000/api/qualify \
  -H "Content-Type: application/json" \
  -d '{
    "lead": {
      "name": "John Doe",
      "phone": "9876543210",
      "email": "john@example.com"
    },
    "mode": "chat",
    "simulate": true
  }'
```

### Search Properties

```bash
curl "http://localhost:8000/api/search?location=Mumbai&property_type=residential&topology=2BHK"
```

## 🎯 Conversation Flow

1. **Greeting** - Verify lead identity
2. **Location** - Collect preferred area
3. **Property Type** - Residential or Commercial
4. **Topology** - BHK type or commercial subtype
5. **Budget** - Budget range (parsed to numeric)
6. **Consent** - Sales representative consent
7. **Search** - Query realtyassistant.in
8. **Closing** - Deliver result and end

## ✅ Qualification Rules

A lead is **QUALIFIED** if ALL conditions are met:
- ✓ Matching properties found > 0
- ✓ Sales consent = Yes
- ✓ Budget successfully parsed to numeric

Otherwise, the lead is **NOT QUALIFIED**.

## 📤 Output Format

### Qualification Summary (JSON)

```json
{
  "session_id": "abc123",
  "lead": {
    "name": "John Doe",
    "phone": "9876543210",
    "email": "john@example.com"
  },
  "collected_data": {
    "contact_name": "John Doe",
    "location": "Mumbai, Andheri",
    "property_type": "residential",
    "topology": "2 BHK",
    "budget_raw": "50 to 60 lakhs",
    "budget_min": 5000000,
    "budget_max": 6000000,
    "sales_consent": true,
    "property_count": 5
  },
  "status": "qualified",
  "reason": {
    "property_count_check": true,
    "consent_check": true,
    "budget_parsed_check": true,
    "summary": "Lead qualified: 5 properties found, consent given, budget parsed successfully."
  },
  "conversation_turns": 14,
  "duration_seconds": 45.2
}
```

### Conversation Transcript

```
Session ID: abc123
Lead: John Doe (9876543210)
Mode: chat
Started: 2024-01-15T10:30:00
Ended: 2024-01-15T10:30:45
==================================================

[Agent]: Hello — this is RealtyAssistant calling about the enquiry you submitted. Am I speaking with John Doe?
[User]: Yes, this is John speaking.
[Agent]: Great, John Doe! Thank you for confirming.
[Agent]: Which location are you searching in?
[User]: Mumbai, Andheri West
...
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | - | Google Gemini API key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.1:8b` | Local LLM model |
| `LLM_TIMEOUT_SECONDS` | `3.5` | Fallback threshold |
| `WHISPER_MODEL` | `base.en` | STT model |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_agent.py::TestQualificationLogic -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

## 📞 Twilio/VAPI Integration

See [docs/INTEGRATION_NOTES.md](docs/INTEGRATION_NOTES.md) for detailed integration instructions.

### Quick Setup

1. Configure webhook URLs in Twilio/VAPI dashboard
2. Add credentials to `.env`
3. Implement TwiML responses in `/webhooks/twilio/voice`

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Server                          │
├─────────────────────────────────────────────────────────────┤
│                    Qualification Agent                       │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │
│  │ Whisper │  │  LLM    │  │ Property│  │   Persistence   │ │
│  │ (STT)   │  │ Engine  │  │ Searcher│  │ (Logs + JSON)   │ │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────────┬────────┘ │
│       │            │            │                 │          │
└───────┼────────────┼────────────┼─────────────────┼──────────┘
        │            │            │                 │
        v            v            v                 v
   ┌────────┐  ┌──────────┐  ┌──────────┐    ┌──────────┐
   │ Audio  │  │ Ollama/  │  │ Realty   │    │  File    │
   │ Input  │  │ Gemini   │  │ Assistant│    │  System  │
   └────────┘  └──────────┘  └──────────┘    └──────────┘
```

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

---

Built with ❤️ for real estate lead qualification.
