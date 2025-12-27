# Integration Notes: Voice & Chat Agent

## Overview
This agent is designed to be deployed as a web service that can handle both chat (via WebSocket/REST) and voice (via Twilio/VAPI) interactions.

## Voice Integration

### 1. Providers Supported
The system supports two voice providers:
- **Twilio**: For traditional SIP/Phone integration.
- **VAPI.ai**: For low-latency AI voice interactions.

### 2. Configuration
Configure the following environment variables in `.env`:

```env
# Choose provider
VOICE_PROVIDER=twilio  # or vapi

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890
WEBHOOK_BASE_URL=https://your-server.com

# VAPI Configuration
VAPI_API_KEY=your_vapi_key
VAPI_ASSISTANT_ID=your_assistant_id
```

### 3. Webhooks
- **Twilio Voice Webhook**: POST `/api/webhooks/twilio/voice`
  - Needs to be configured in the Twilio Console for the phone number.
  - Returns TwiML to control the call.
- **VAPI Webhook**: VAPI handles the call flow, but can be configured to hit your server for logic.

### 4. Audio-to-Text (ASR)
- The system uses **OpenAI Whisper** (via `WhisperEngine`) for transcribing user audio if processing raw audio streams.
- For VAPI, transcription is handled by their platform and sent as text.

### 5. Retries & Backoffs
The `VoiceHandler` implements robust error handling:
- **Misunderstandings**: If the confidence score is low (< 0.6), the agent asks for clarification.
- **Silence/No Input**: Re-prompts the user up to 2 times before gracefully ending or transferring.
- **API Failures**: If the property search fails, the agent falls back to a general "We'll have an expert call you" response to ensure the lead isn't lost.

## Chat Integration

### 1. API Endpoints
- **Trigger Qualification**: `POST /api/qualify`
  - Payload: `{ "lead": { "name": "...", "phone": "..." }, "mode": "chat" }`
  - Returns: Full qualification summary JSON.

### 2. Frontend Widget
- A `widget.js` script is provided to embed the chat interface on any website.
- It automatically handles the conversation flow defined in `prompts/conversation_templates.json`.

## Data Persistence
- **Transcripts**: Saved to `data/logs/` as `.txt` files.
- **Summaries**: Saved to `data/leads/` as `.json` files.
- **Database**: SQLite/PostgreSQL supported via `core/database.py`.

## Property Search Engine
- Uses **Playwright** for real-time scraping of `realtyassistant.in`.
- **Selectors**: Tightly coupled to the site's HTML structure (verified).
- **Headless**: Runs in background, invisible to the user.
