# Simulated Bug Reports

**Project:** RealtyAssistant AI Agent  
**Date:** 2025-12-27  

---

## Bug Report #1: Budget Parsing Failure for Mixed Indian Units

**Title**: Budget parser fails when user mixes "Crore" and "Lakhs" in range format (e.g., "90 Lakhs to 1.2 Crore").  
**Severity**: Medium (Functional Issue)  
**Priority**: P2

### Steps to Reproduce
1. Initiate a voice or chat session.
2. Navigate to the Budget stage.
3. User input: "My budget is around 90 lakhs to 1.2 crore."
4. Observe the agent's acknowledgment and persistence log.

### Expected Result
The agent should parse:
*   Min: 9,000,000 (90 Lakhs)
*   Max: 12,000,000 (1.2 Crores)
And acknowledge "Noted budget between 90 Lakhs and 1.2 Crores".

### Actual Result
The agent sometimes fails to parse the mixed unit range correctly, defaulting to `Min: 90` or `None`, asking the user to repeat. In some cases, it parses "1.2" as just 1.2 rupees.

### Screenshots
*(Placeholder: Chat log showing "I didn't quite catch that budget range" response)*

---

## Bug Report #2: Search Timeouts on "All India" Queries

**Title**: Property Search times out when Location is generic or "All India".  
**Severity**: High (Component Failure)  
**Priority**: P1

### Steps to Reproduce
1. Start Search API directly or via Chat.
2. Provide `location=""` (empty) or broad term like "India".
3. Provide valid `property_type="Residential"`.
4. Observe the response time and final result.

### Expected Result
The system should either:
a) Return a fast "Please specify a city" error.
b) Perform a limited search (top 10 results).
c) Return results within 30 seconds.

### Actual Result
The Playwright scraper attempts to load the root directory listing for all properties, causing a 60s+ timeout or a browser crash due to DOM size, resulting in a 500 Internal Server Error.

### Screenshots
*(Placeholder: Postman 500 Error output with "Timeout Exceeded" message)*

---

## Bug Report #3: Voice Handling for Heavy Background Noise

**Title**: Voice Handler hallucinates inputs when background noise is high.  
**Severity**: Low (Edge Case)  
**Priority**: P3

### Steps to Reproduce
1. Initiate Voice Call.
2. Speak clearly but with loud street ambience (traffic noise) in background.
3. Say "I am looking for a flat in Noida."

### Expected Result
Whisper/VAPI should filter noise or return low confidence score, prompting for repetition if unclear.

### Actual Result
The system sometimes transcribes noise as random words (e.g., "honk car stop") and attempts to match them to city names (e.g., "honk" -> "Hong Kong" or similar hallucination), leading to incorrect location recognition.

### Screenshots
*(Placeholder: Transcript log showing `User: [Traffic Noise Interpreted as Text]`)*
