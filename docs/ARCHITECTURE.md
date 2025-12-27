# RealtyAssistant AI Architecture

## System Overview

RealtyAssistant is a high-availability AI agent designed for real estate lead qualification. It operates as a dual-channel system (Voice & Chat) that funnels valid leads into a robust, fail-safe database while providing real-time property intelligence.

### High-Level Components

```mermaid
graph TD
    Client[User / Client] -->|HTTP/WebSocket| Nginx[Nginx Reverse Proxy]
    Nginx -->|Port 20000| FastAPI[FastAPI Server]
    
    subgraph "Core Agent Logic"
        FastAPI --> Agent[Qualification Agent]
        Agent --> Voice[Voice Handler]
        Agent --> Chat[Chat Widget]
    end
    
    subgraph "Intelligence Layer"
        Voice --> Whisper[Whisper STT (Local)]
        Voice --> Fuzzy[Fuzzy Matcher]
        Voice --> LLM[LLM Engine]
        Chat --> LLM
    end
    
    subgraph "External Services"
        LLM -->|Primary| Ollama[Ollama (Local)]
        LLM -->|Fallback| Gemini[Google Gemini API]
        Agent -->|Search| Searcher[Property Searcher]
        Searcher -->|Scrape| Web[RealtyAssistant.in]
    end
    
    subgraph "Persistence Layer"
        Agent --> DBWrapper[Fail-Safe DB Wrapper]
        DBWrapper -->|Write Lead| SQLite[SQLite Database (leads.db)]
        DBWrapper -->|Backup| JSON[JSON Fallback]
    end
```

## Core Modules

### 1. Voice Handler (`core/voice_handler.py`)
The voice system is designed to handle the nuances of Indian English accents and telephonic audio quality.

- **Fuzzy Matching**: Uses `SequenceMatcher` and phonetic algorithms to map variations like "Noyda", "Gurgaon", "Two BHK" to canonical values (`Noida`, `Gurugram`, `2 BHK`).
- **Rich Input Extraction**: Can parse complex sentences ("I want a 3 BHK in Noida under 50 lakhs") into structured JSON using the LLM.
- **State Machine**: Maintains conversation state (Greeting -> Location -> Category...) but allows jumping if the user provides information early.
- **LLM Enhancement**: Uses `gemini-2.0-flash-exp` (via fallback) or local Gemma models to "humanize" scripted responses.

### 2. Fail-Safe Database (`core/database.py`)
The database layer is engineered to never lose a lead, even in the event of file corruption or disk errors.

- **Auto-Healing**: On startup and before every write, the system checks SQLite integrity.
- **Recovery Pipeline**:
    1.  **Detect**: `PRAGMA integrity_check` fails.
    2.  **Backup**: Corrupt DB is copied to `_backup_timestamp.db`.
    3.  **Recover**: Raw extraction of readable rows from the corrupt file.
    4.  **Reset**: Corrupt DB file is deleted and re-initialized.
    5.  **Restore**: Recovered data is inserted into the fresh DB.
- **In-Memory Fallback**: If disk I/O fails repeatedly, it switches to an in-memory SQLite database to keep the app running (logging errors for admin).

### 3. Property Searcher (`core/search_scout.py`)
A headless browser automation tool that queries correct real estate data in real-time.

- **Dynamic Scraping**: Navigates `realtyassistant.in` using Playwright.
- **Result Parsing**: Extracts pricing, location, and images to show "Property Cards" to the user.
- **Headless Optimization**: Runs efficiently on server/VM environments without a GUI.

## Deployment Architecture

The system is designed to be "One-Click" deployable on both Windows (Dev) and Linux (Prod).

### Production (Ubuntu VM)
- **Service Management**: `systemd` manages the `realtyassistant` service.
- **Reverse Proxy**: Nginx handles SSL and forwards `/task1/` traffic to internal port `20000`.
- **Isolation**: Runs in a Python `venv` to avoid system conflicts.

### Development (Windows)
- **Automation**: `run_project.bat` handles Python checks, `venv` creation, dependency installation, and port conflict resolution.
- **Port**: Defaults to `20000`.

## Data Flow

1.  **Input**: User speaks or types.
2.  **Processing**:
    -   **Voice**: Audio -> Whisper STT -> Text -> Fuzzy Match/LLM -> Intent.
    -   **Chat**: Text -> LLM -> Intent.
3.  **Action**:
    -   If requirements gathered: Trigger `PropertySearcher`.
    -   If result found: AI summarizes and asks for consent.
4.  **Conversion**:
    -   User agrees -> Contact info collected -> Data saved to `leads.db`.
    -   Email summary sent via SMTP.

## Directory Structure

```
chat-agent/
├── core/                  # Business Logic
│   ├── database.py        # Fail-safe DB
│   ├── voice_handler.py   # Voice intelligence
│   └── search_scout.py    # Web scraper
├── data/                  # Persistent Storage
│   ├── leads.db           # Main database
│   ├── leads/             # JSON backups
│   └── logs/              # Transcripts
├── frontend/              # User Interface
│   ├── widget.js          # Embeddable Chat
│   └── voice.html         # Voice Demo UI
└── main.py                # FastAPI Entry Point
```
