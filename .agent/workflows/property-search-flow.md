---
description: Property Search Chat Flow - Complete workflow matching realtyassistant.in form
---

# Property Search Chat Flow Workflow

This workflow describes the complete conversation flow for qualifying leads through the chat widget, matching ALL fields from the realtyassistant.in property search form.

## NEW Conversation Flow (Updated)

```
name → location → property_category → property_type → bedroom → project_status 
→ possession → SEARCH & SHOW RESULTS → consent_after_search 
→ IF YES: budget → phone → email → SAVE TO DB → complete
→ IF NO: SAVE MINIMAL TO DB → thank_you
```

### Key Changes:
1. **User details are collected AFTER search results are shown**
2. **Consent is asked AFTER showing matching properties**
3. **If user declines, we thank them and end (no contact details collected)**
4. **If user agrees, we collect budget, phone, email**
5. **All leads are saved to SQLite database (not JSON files)**

## Form Fields Mapping

### Search Fields (Collected First):
| Field | Description | Options |
|-------|-------------|---------|
| name | User's name | Free text |
| location | City | 16 cities from form |
| property_category | Residential/Commercial | 2 options |
| property_type | Subtype | Dynamic based on category |
| bedroom | BHK | 1-5 BHK, Studio |
| project_status | Construction status | 4 options |
| possession | Possession timeline | 5 options |

### Contact Fields (Only if user consents):
| Field | Description |
|-------|-------------|
| budget | Budget range (e.g., 50 lakhs) |
| phone | Phone number |
| email | Email address |
| consent | Yes (agreed to be called) |

## URL Construction

The search generates a GET URL like:
```
https://realtyassistant.in/properties?city=10&property_category=1&property_type=Apartments&bedroom=3+BHK&project_status=Under+Construction&possession=1+year&submit=Search
```

## Database Schema

Leads are stored in SQLite (`data/leads.db`):

```sql
CREATE TABLE leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(50) UNIQUE NOT NULL,
    created_at DATETIME,
    updated_at DATETIME,
    
    -- Contact info (NULL if user declined)
    name VARCHAR(255),
    phone VARCHAR(20),
    email VARCHAR(255),
    consent BOOLEAN DEFAULT FALSE,
    
    -- Search preferences
    location VARCHAR(255),
    property_category VARCHAR(100),
    property_type VARCHAR(100),
    bedroom VARCHAR(50),
    project_status VARCHAR(100),
    possession VARCHAR(100),
    budget VARCHAR(100),
    
    -- Search results
    properties_found INTEGER DEFAULT 0,
    search_url TEXT,
    
    -- Qualification
    qualified BOOLEAN DEFAULT FALSE
);
```

## Workflow Steps

// turbo-all

### 1. Start Development Server
```bash
cd R:\chat-agent && python main.py
```

### 2. Test Chat Flow
- Open browser to http://localhost:8080/demo
- Click chat bubble
- Enter name → Answer search questions → See results
- Test YES path: Accept call → Enter budget, phone, email → See final summary
- Test NO path: Decline call → See thank you message

### 3. Verify Database Storage
```bash
# View leads in database
sqlite3 data/leads.db "SELECT * FROM leads ORDER BY created_at DESC LIMIT 10"

# Or use API
curl http://localhost:8080/api/leads
```

### 4. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/leads | Get all leads (with pagination) |
| GET | /api/leads?qualified_only=true | Get only qualified leads |
| POST | /api/leads | Create/update a lead |
| GET | /api/leads/{session_id} | Get lead by session ID |
| GET | /api/search | Search properties |

## Implementation Files

- **Frontend Widget**: `frontend/widget.js` - CONVERSATION_FLOW object
- **Property Search**: `core/search_scout.py` - Playwright scraper
- **Database**: `core/database.py` - SQLite ORM with SQLAlchemy
- **API Endpoints**: `main.py` - REST API

## Testing Checklist

- [ ] Search fields collected before showing results
- [ ] Property search returns real results from realtyassistant.in
- [ ] Top 3 properties displayed with links
- [ ] Consent asked AFTER results shown
- [ ] YES path: budget, phone, email collected
- [ ] NO path: thank you message, no contact collection
- [ ] Lead saved to database (not JSON files)
- [ ] GET /api/leads returns leads from database
- [ ] Qualified leads have consent=true, properties_found>0, contact info
