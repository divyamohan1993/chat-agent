# RealtyAssistant AI Agent - Twilio/VAPI Integration Notes

## Overview

This document provides integration notes for connecting the RealtyAssistant AI Agent to voice calling platforms like Twilio and VAPI.ai.

---

## Twilio Integration

### Prerequisites

1. Twilio account with Voice capabilities
2. A Twilio phone number
3. API credentials (Account SID and Auth Token)

### Configuration

Add the following to your `.env` file:

```env
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

### Webhook Setup

1. Configure your Twilio phone number's Voice webhook to point to:
   ```
   https://your-domain.com/webhooks/twilio/voice
   ```

2. Set the HTTP method to `POST`

### Call Flow

1. **Inbound Call**: User calls the Twilio number
2. **Webhook Trigger**: Twilio sends request to `/webhooks/twilio/voice`
3. **TwiML Response**: Server responds with TwiML to gather speech
4. **Transcription**: Use Twilio's `<Gather>` with `input="speech"` or integrate Whisper
5. **Agent Processing**: Pass transcription to qualification agent
6. **Response**: Convert agent response to speech using TwiML `<Say>` or `<Play>`

### Sample TwiML Response

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" timeout="3" speechTimeout="auto" action="/webhooks/twilio/process">
        <Say voice="Polly.Joanna">
            Hello, this is RealtyAssistant calling about your enquiry. Am I speaking with John?
        </Say>
    </Gather>
    <Say>We didn't receive any input. Goodbye!</Say>
</Response>
```

### Retry/Backoff Strategy

- **Connection failures**: Retry up to 3 times with exponential backoff (1s, 2s, 4s)
- **API rate limits**: Respect Twilio's rate limits (1 request/second for trial accounts)
- **Timeout**: Set webhook timeout to 15 seconds

---

## VAPI.ai Integration

### Prerequisites

1. VAPI.ai account
2. API key

### Configuration

```env
VAPI_API_KEY=your_vapi_api_key
```

### Webhook Setup

1. In VAPI dashboard, configure the webhook URL:
   ```
   https://your-domain.com/webhooks/vapi/call
   ```

2. Enable the following events:
   - `call.started`
   - `transcript.update`
   - `call.ended`

### Call Flow with VAPI

1. **Create Assistant**: Configure VAPI assistant with the system prompt
2. **Initiate Call**: Use VAPI API to start outbound call
3. **Real-time Events**: VAPI sends transcript updates to webhook
4. **Agent Integration**: Process transcripts and return responses

### Sample VAPI API Call

```python
import requests

def initiate_vapi_call(lead):
    response = requests.post(
        "https://api.vapi.ai/call",
        headers={
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "assistantId": "your_assistant_id",
            "phoneNumber": lead.phone,
            "metadata": {
                "lead_name": lead.name,
                "lead_email": lead.email
            }
        }
    )
    return response.json()
```

### Retry/Backoff Strategy

- **Failed calls**: Retry after 30 seconds, then 2 minutes, then 10 minutes
- **No answer**: Leave voicemail option or schedule callback
- **API errors**: Exponential backoff with max 3 retries

---

## Audio-to-Text Implementation

### Local Whisper (Preferred for Latency)

The system uses `faster-whisper` for local speech-to-text:

```python
from core.whisper_engine import WhisperEngine

whisper = WhisperEngine(
    model_name="base.en",  # or "distil-large-v3" for better accuracy
    device="cpu",
    compute_type="int8"
)

# Transcribe audio
text, confidence = whisper.transcribe(audio_data, sample_rate=16000)
```

### Twilio Speech Recognition

Twilio provides built-in speech recognition via `<Gather>`:

```xml
<Gather input="speech" language="en-IN" speechModel="phone_call">
    <Say>Please tell me your location preferences.</Say>
</Gather>
```

### VAPI Built-in Transcription

VAPI handles transcription automatically and sends updates via webhook.

---

## Error Handling

### Network Errors

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
async def make_api_call():
    # API call logic
    pass
```

### Fallback Behavior

| Scenario | Action |
|----------|--------|
| Twilio API down | Queue call for retry in 5 minutes |
| VAPI timeout | Fallback to chat mode |
| Whisper fails | Use Twilio/VAPI built-in transcription |
| LLM timeout | Fallback to Gemini API |

### Logging

All calls and errors are logged with:
- Session ID
- Timestamp
- Error details
- Request/Response bodies (sanitized)

---

## Security Considerations

1. **Webhook Validation**: Validate Twilio request signatures
2. **API Key Protection**: Store keys in environment variables
3. **Data Encryption**: Use HTTPS for all webhooks
4. **PII Handling**: Don't log sensitive data like full phone numbers

### Twilio Signature Validation

```python
from twilio.request_validator import RequestValidator

def validate_twilio_request(request):
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    url = request.url
    signature = request.headers.get("X-Twilio-Signature")
    params = request.form
    return validator.validate(url, params, signature)
```

---

## Testing

### Mock Call Simulation

```bash
# Simulate a call flow
python main.py simulate --name "John Doe" --phone "9876543210"
```

### Twilio Test Credentials

Use Twilio test credentials for development:
- Test Account SID: `AC...test`
- Test Auth Token: Available in Twilio console

### VAPI Sandbox

Use VAPI sandbox mode for testing without incurring costs.

---

## Production Checklist

- [ ] SSL certificate configured
- [ ] Webhook URLs accessible from public internet
- [ ] API keys stored securely
- [ ] Logging configured
- [ ] Error monitoring setup (e.g., Sentry)
- [ ] Rate limiting implemented
- [ ] Backup LLM (Gemini) configured
- [ ] Database backup strategy
- [ ] Call recording consent (if applicable)
