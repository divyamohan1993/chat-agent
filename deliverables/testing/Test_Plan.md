# Test Plan: RealtyAssistant AI Agent

**Version:** 1.0  
**Date:** 2025-12-27  
**Author:** QA Team  
**Status:** Draft  

---

## 1. Objective
The objective of this Test Plan is to define the strategy, scope, and approach for validating the **RealtyAssistant AI Agent**. This ensures the system accurately qualifies leads via Voice and Chat interfaces, performs real-time property searches on `realtyassistant.in`, and correctly persists data, meeting the requirements of "Task A".

## 2. Scope
The scope of testing includes the following modules and functionalities:
*   **Conversational Logic**: Verification of the Greeting, Location, Type, Topology, Budget, and Consent flow.
*   **Voice Integration**: Speech-to-Text accuracy, latency, and handling of Indian accents/variations.
*   **Backend API**: Functional testing of FastAPI endpoints (`/api/qualify`, `/api/search`, `/api/leads`).
*   **Scraping Engine**: Reliability and accuracy of the Playwright-based property searcher.
*   **Data Persistence**: Verification of JSON summary generation and transcript logging.
*   **Chat Widget**: Frontend widget integration and message handling.

## 3. Out of Scope
*   **Third-Party Down-Time**: Performance issues stemming directly from `realtyassistant.in` downtime (though handling logic is in scope).
*   **Telephony Provider Infrastructure**: Internal testing of Twilio/VAPI networks.
*   **Load Testing**: High-concurrency stress testing (>1000 concurrent calls) is deferred to Phase 2.

## 4. Test Strategy
We will employ a mix of automated and manual testing approaches:
*   **Automated Unit Tests**: For data models (`models.py`) and utility functions (budget parsing).
*   **API Testing**: Using Postman to validate request/response schemas and error codes.
*   **Manual Exploratory Testing**: For Voice interaction (simulating various accents and noise levels).
*   **Integration Testing**: End-to-end flow from Lead -> Call -> Search -> Qualification -> Database.

## 5. Risks & Assumptions
### Risks
*   **Site Structure Changes**: `realtyassistant.in` DOM changes could break the scraper. *Mitigation: Strict selectors and error handling.*
*   **ASR Accuracy**: Heavy accents may lead to misinterpretation. *Mitigation: Fuzzy matching and LLM fallback implementation.*
*   **Latency**: LLM + Search latency might exceed voice capability tolerance. *Mitigation: Async processing and filler phrases.*

### Assumptions
*   The `realtyassistant.in` website is accessible from the deployment region.
*   OpenAI/Gemini and Voice Provider APIs are operational.
*   Test environment has necessary API keys configured.

## 6. Entry & Exit Criteria
### Entry Criteria
*   Code frozen and deployed to staging environment.
*   All environment variables (`API_KEYS`, `DB_PATH`) configured.
*   Smoke test passed (Server starts, Health check returns 200 OK).

### Exit Criteria
*   95% of High-Priority test cases passed.
*   Zero Critical or Blocker bugs open.
*   Voice flow completes successfully for standard accents.
*   Property search returns accurate data comparisons.

---
