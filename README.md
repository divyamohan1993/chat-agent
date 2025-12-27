# RealtyAssistant AI Agent

> **Production-Ready AI Voice & Chat Agent for Real Estate Lead Qualification**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🏠 Overview

**RealtyAssistant** is an advanced AI system designed to qualify real estate leads through natural voice conversations and intelligent chat interactions. Unlike simple chatbots, it features a **fail-safe architecture**, **dynamic accent understanding**, and **real-time property search** capabilities.

It is designed to run on a cheap VPS (Ubuntu) or local Windows machine with a single "One-Click" setup command.

### Key Features

- **🎙️ Natural Voice Interface**:
  - Handles Indian accents (Noida, Gurugram, etc.) via fuzzy matching.
  - "Rich Input" processing: "I want a 3 BHK in Noida under 50 lakhs" is understood instantly.
  - Voice-to-Text via local Whisper engine.
- **🛡️ Fail-Safe Leads Database**:
  - **Auto-Healing**: Automatically detects and repairs database corruption.
  - **Zero-Loss**: Falls back to in-memory processing if disk fails, ensuring leads are captured in logs.
  - **Structured Storage**: SQLite database tracking every conversation detail.
- **🔍 Live Intelligence**:
  - Scrapes `realtyassistant.in` in real-time to show actual property listings.
  - Hybrid LLM (Ollama + Gemini Fallback) for robust understanding.
- **🚀 Production Ready**:
  - Runs on Port `20000` (configurable).
  - Includes Nginx configs and systemd service files.
  - One-click deployment scripts for Windows and Linux.

## 🚀 Quick Start (One-Click)

### Windows (Development)

Double-click `run_project.bat` or run in terminal:

```batch
run_project.bat
```

**This script automatically:**
1. ✅ Checks for Python 3.10+.
2. ✅ Creates a virtual environment.
3. ✅ Installs all dependencies.
4. ✅ Frees up Port 20000 if occupied.
5. ✅ Starts the Server.

> **Access:** [http://localhost:20000/demo](http://localhost:20000/demo)

### Linux (Production / VM)

```bash
sudo bash run_project.sh
```

**This script automatically:**
1. ✅ Installs System Dependencies (Python, Nginx, etc.).
2. ✅ Sets up the AI Environment.
3. ✅ Configures Nginx Reverse Proxy.
4. ✅ Installs it as a background Systemd Service.

> **Access:** `https://<your-ip>/task1/demo`

## 🏗️ Architecture

For a deep dive into the system design, fail-safe mechanisms, and voice pipeline, see [**ARCHITECTURE.md**](docs/ARCHITECTURE.md).

```
┌──────────────┐      ┌─────────────┐      ┌───────────────┐
│  Voice/Chat  │      │  Analysis   │      │  Persistence  │
│  Interface   │ ───> │   Engine    │ ───> │   Database    │
└──────────────┘      └──────┬──────┘      └───────┬───────┘
                             │                     │
                      ┌──────▼──────┐      ┌───────▼───────┐
                      │  Property   │      │   Fail-Safe   │
                      │  Searcher   │      │   Mechanism   │
                      └─────────────┘      └───────────────┘
```

## 🔧 Configuration

The application is configured via `.env`. A default one is created automatically if missing.

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `20000` | Application Port |
| `GEMINI_API_KEY` | - | Required for AI fallback |
| `DATABASE_URL` | `sqlite:///data/leads.db` | Main database path |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local LLM URL |
| `VOICE_PROVIDER` | `twilio` | `twilio` or `vapi` |

## 📡 API Endpoints

### Core
- **GET** `/demo` - Chat Widget Interface
- **GET** `/voice` - Voice Testing Interface
- **GET** `/leads` - Admin Dashboard for Leads

### API
- **POST** `/api/qualify` - Submit lead data
- **POST** `/api/leads` - Create lead entry
- **GET** `/api/leads` - Fetch lead history
- **POST** `/api/voice/process` - Handle audio chunk

## 🧪 Testing Voice

1. Navigate to [http://localhost:20000/voice](http://localhost:20000/voice).
2. Click the **Microphone** button.
3. Speak naturally. Try saying:
   > *"Hi, I am looking for a 3 BHK apartment in Noida Extension."*
4. The system will:
   - Recognize your speech.
   - Extract "3 BHK", "Apartment", "Noida Extension".
   - Skip redundant questions and verify your details.
   - Search for properties.

## 📄 License

MIT License. Built with ❤️ by [dmj.one](https://dmj.one).
