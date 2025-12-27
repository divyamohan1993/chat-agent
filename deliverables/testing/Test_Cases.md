# Test Case Document: RealtyAssistant AI Agent

**Test Suite ID:** RA-2025  
**Total Cases:** 20  

---

## 1. Functional Testing (Conversational & Logic)

| ID | Test Case Title | Pre-Conditions | Steps | Expected Result | Priority |
|:---|:---|:---|:---|:---|:---|
| **TC01** | **Happy Path - Standard Residential** | Agent initialized | 1. User says "Hello"<br>2. Confirm name<br>3. Location: "Noida"<br>4. Type: "Residential"<br>5. Topo: "3 BHK"<br>6. Budget: "1 Cr"<br>7. Consent: "Yes" | Agent collects all fields, triggers search, reports count > 0, and qualifies lead. | High |
| **TC02** | **Happy Path - Commercial Office** | Agent initialized | 1. Location: "Mumbai"<br>2. Type: "Commercial"<br>3. Type: "Office"<br>4. Budget: "5 Crores" | Agent correctly branches to Commercial flow, asking "Shop/Office", and qualifies lead. | High |
| **TC03** | **Budget Parsing - Range Input** | Conversational State | User says "Budget is between 50 to 60 lakhs" | System extracts `min: 5000000` and `max: 6000000`. | Medium |
| **TC04** | **Budget Parsing - Mixed Units** | Conversational State | User says "1.5 CR" | System parses as `15000000`. | Medium |
| **TC05** | **Location Fuzzy Matching** | Conversational State | User says "Noyda" or "Ggn" | System maps to "Noida" and "Gurugram" respectively. | High |
| **TC06** | **Topology Extraction - Conversational** | Conversational State | User says "I need a three bedroom flat" | System extracts "3 BHK" and Property Type "Apartment". | Medium |
| **TC07** | **Consent - Soft Rejection** | Consent Stage | User says "Not right now, maybe later" | System interprets as `Consent: False`, marks `Not Qualified`. | High |
| **TC08** | **Name Correction Flow** | Greeting Stage | Agent asks "Am I speaking with John?" -> User: "No, this is Mike" | Agent updates `contact_name` to "Mike" and proceeds. | Medium |

## 2. API Testing

| ID | Test Case Title | Endpoint | Payload / Params | Expected Result | Priority |
|:---|:---|:---|:---|:---|:---|
| **TC09** | **Qualify API - Valid Lead** | `POST /api/qualify` | `{"lead": {"name": "Test", "phone": "9999999999"}, "mode": "chat"}` | Returns 200 OK, JSON Summary with `status: QUALIFIED` (simulated). | High |
| **TC10** | **Qualify API - Invalid Phone** | `POST /api/qualify` | `{"lead": {"name": "Test", "phone": "123"}}` | Returns 422 Validation Error (Phone length < 10). | High |
| **TC11** | **Search API - Basic Search** | `GET /api/search` | `?location=noida&budget_max=5000000` | Returns `count` (integer), `success: true`. | High |
| **TC12** | **Search API - No Results** | `GET /api/search` | `?location=Mars&property_type=Residential` | Returns `count: 0`, `success: true` (or valid error matching site). | Medium |
| **TC13** | **Leads API - Retrieval** | `GET /api/leads` | None | Returns list of JSON summaries. | Medium |
| **TC14** | **Status API - Health Check** | `GET /api/status` | None | Returns `status: operational`, component checks valid. | Low |

## 3. Negative & Security Testing

| ID | Test Case Title | Type | Steps | Expected Result | Priority |
|:---|:---|:---|:---|:---|:---|
| **TC15** | **Empty Audio Input** | Negative | Send blank audio or silence to Voice Handler | Agent prompts "I didn't catch that", increments retry count. | Medium |
| **TC16** | **SQL/Script Injection in Name** | Security | Submit Lead Name: `<script>alert(1)</script>` | System sanitizes input; Script does NOT execute in Dashboard/Logs. | High |
| **TC17** | **Large Payload Attack** | Security | Send `POST /api/qualify` with 10MB JSON body | Server rejects with 413 Entity Too Large or validation timeout. | Medium |
| **TC18** | **Property Search Timeout** | Negative | Simulate `realtyassistant.in` being unresponsive | Searcher returns `success: false` after 45s, Agent handles gracefully ("We'll check offline"). | High |

## 4. AI Behavior Testing

| ID | Test Case Title | Scenario | Expected Result | Priority |
|:---|:---|:---|:---|:---|
| **TC19** | **Context Retention** | User gives Location "Pune" in step 2, then asks "What city did I say?" in step 5. | (Optional) LLM context aware, or Agent maintains flow without crashing. | Low |
| **TC20** | **Hallucination Check** | User asks "Can you order pizza?" | Agent politely declines/redirects to Real Estate topic. | Medium |

---
