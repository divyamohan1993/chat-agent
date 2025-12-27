# RealtyAssistant AI Chat/Voice Agent

## Overview
This is a production-ready AI agent tailored for `realtyassistant.in` property qualification. It acts as a frontline sales development representative (SDR), qualifying leads via Voice or Chat before passing them to human sales reps.

## Deliverables Structure

### 1. Agent Code (`agent_code/`)
Contains the complete source code for the agent.
- `agent.py`: The core qualification logic and state machine.
- `main.py`: FastAPI server exposing endpoints for Voice, Chat, and Search.
- `models.py`: Pydantic data models for strict validation.
- `core/`:
  - `voice_handler.py`: Advanced voice processing with fuzzy matching for Indian accents.
  - `search_scout.py`: Playwright-based scraper for `realtyassistant.in`.
  - `llm_engine.py`: Wrapper for LLM interactions.

### 2. Prompt Templates (`prompt_templates/`)
- `conversation_templates.json`: The rigid script used for the deterministic conversation flow.
- `system_prompt.md`: The persona definition for the AI.
- `prompt_templates.md`: Various prompts for extraction and logic.

### 3. Integration Notes (`integration_notes.md`)
Detailed instructions on how to hook this up with Twilio, VAPI, and your frontend.

## Key Features
1.  **Strict Script Adherence**: Follows the defined flow (Greeting -> Location -> Type -> Topology -> Budget -> Consent).
2.  **Real-time Availability Check**: Queries `realtyassistant.in` live during the call/chat.
3.  **Deterministic Qualification**: Returns a strictly typed JSON summary with `Qualified` or `Not Qualified` status.
4.  **Full Persistence**: Saves every conversation transcript and analysis JSON.

## quick Start
1.  Navigate to `agent_code/`.
2.  Install dependencies: `pip install -r requirements.txt` (create this if missing based on imports).
3.  Run server: `python main.py` or via Uvicorn.
4.  Test Chat: Open `http://localhost:8000/demo`.
5.  Test Search logic: `http://localhost:8000/api/search?location=noida&budget_max=5000000`.

## Requirements
- Python 3.9+
- Playwright (`playwright install`)
- Connect to an LLM (Ollama or Gemini/OpenAI).
