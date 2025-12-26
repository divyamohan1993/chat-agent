# =============================================================================
# RealtyAssistant AI Agent - Main Entry Point
# =============================================================================
"""
FastAPI server and CLI entry point for the RealtyAssistant AI Agent.
Provides REST API endpoints and command-line interface for lead qualification.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

# Load environment variables
load_dotenv()

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from models import (
    LeadInput, APILeadRequest, APIResponse,
    QualificationSummary, QualificationStatus,
    CollectedData, QualificationReason
)
from agent import QualificationAgent
from core import LLMEngine, PropertySearcher, WhisperEngine, GeminiFallback

# Configure logging
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)

logger = logging.getLogger(__name__)


# =============================================================================
# Application Lifecycle
# =============================================================================

# Global instances
_agent: Optional[QualificationAgent] = None
_llm_engine: Optional[LLMEngine] = None
_property_searcher: Optional[PropertySearcher] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    global _agent, _llm_engine, _property_searcher
    
    logger.info("Starting RealtyAssistant AI Agent...")
    
    # Create directories
    Path("data/logs").mkdir(parents=True, exist_ok=True)
    Path("data/leads").mkdir(parents=True, exist_ok=True)
    
    # Initialize components
    _llm_engine = LLMEngine(
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "3.5")),
        enable_fallback=os.getenv("ENABLE_GEMINI_FALLBACK", "true").lower() == "true"
    )
    
    _property_searcher = PropertySearcher(headless=True)
    
    _agent = QualificationAgent(
        llm_engine=_llm_engine,
        property_searcher=_property_searcher,
        logs_dir=os.getenv("LOGS_DIR", "data/logs"),
        leads_dir=os.getenv("LEADS_DIR", "data/leads")
    )
    
    # Initialize engine
    await _llm_engine.initialize()
    
    logger.info("RealtyAssistant AI Agent ready!")
    
    yield
    
    # Cleanup
    logger.info("Shutting down...")
    if _property_searcher:
        await _property_searcher.close()


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="RealtyAssistant AI Agent",
    description="AI Voice/Chat Agent for Real Estate Lead Qualification",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend static files
frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="frontend")
    
    @app.get("/demo", response_class=FileResponse)
    async def demo_page():
        """Serve the demo page."""
        return FileResponse(frontend_dir / "index.html")
    
    @app.get("/voice", response_class=FileResponse)
    async def voice_page():
        """Serve the voice testing page."""
        return FileResponse(frontend_dir / "voice.html")
    
    @app.get("/widget.js", response_class=FileResponse)
    async def widget_js():
        """Serve the widget JavaScript."""
        return FileResponse(frontend_dir / "widget.js", media_type="application/javascript")


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", response_class=JSONResponse)
async def root():
    """Root endpoint with API info."""
    return {
        "name": "RealtyAssistant AI Agent",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "qualify": "/api/qualify - POST lead for qualification",
            "status": "/api/status - GET system status",
            "leads": "/api/leads - GET all lead summaries",
            "search": "/api/search - GET property search"
        }
    }


@app.get("/api/status")
async def get_status():
    """Get system status and component availability."""
    global _llm_engine, _property_searcher
    
    return {
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "llm_engine": _llm_engine.get_status() if _llm_engine else None,
            "property_searcher": {
                "available": _property_searcher.is_available() if _property_searcher else False
            }
        }
    }


@app.post("/api/qualify", response_model=APIResponse)
async def qualify_lead(request: APILeadRequest, background_tasks: BackgroundTasks):
    """
    Trigger lead qualification flow.
    
    Args:
        request: Lead request with lead info and mode
        
    Returns:
        Qualification result or job ID for async processing
    """
    global _agent
    
    if not _agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        # Check if we have pre-collected data (from chat widget)
        if request.collected_data:
            # Parse collected data
            data_dict = request.collected_data
            
            # Map fields safely
            c_data = CollectedData(
                contact_name=data_dict.get("name") or request.lead.name,
                location=data_dict.get("location"),
                property_category=data_dict.get("property_category"),
                property_type=data_dict.get("property_type"),
                bedroom=data_dict.get("bedroom"),
                sales_consent=str(data_dict.get("consent", "")).lower() == "true",
                property_count=0  # Should be passed from frontend ideally, or default to 0
            )
            
            # Determine status
            status = QualificationStatus.QUALIFIED if c_data.sales_consent else QualificationStatus.NOT_QUALIFIED
            
            # Create reason
            reason = QualificationReason(
                property_count_check=True, # Assumed true if they got this far
                consent_check=c_data.sales_consent or False,
                summary=f"Lead submitted via chat widget. Status: {status.value}"
            )
            
            # Create summary
            summary = QualificationSummary(
                session_id=f"widget-{datetime.now().strftime('%H%M%S')}-{request.lead.phone[-4:]}",
                lead=request.lead,
                collected_data=c_data,
                status=status,
                reason=reason,
                property_search_url="",
                conversation_turns=0,
                duration_seconds=0
            )
            
            # Save using agent's leads_dir
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(x for x in request.lead.name if x.isalnum() or x in " -_").strip()
            filename = f"{timestamp}_{safe_name}_summary.json"
            save_path = Path(os.getenv("LEADS_DIR", "data/leads")) / filename
            
            with open(save_path, "w", encoding="utf-8") as f:
                import json
                json.dump(summary.model_dump(mode="json"), f, indent=2, default=str)
                
            logger.info(f"Saved widget lead to {save_path}")
            
            return APIResponse(
                success=True,
                message=f"Lead saved successfully",
                data=summary.model_dump(mode="json")
            )

        # Run qualification simulation (original logic)
        summary = await _agent.qualify_lead(
            lead=request.lead,
            mode=request.mode,
            user_input_handler=None  # Simulation mode
        )
        
        return APIResponse(
            success=True,
            message=f"Lead {summary.status.value}",
            data=summary.model_dump(mode="json")
        )
        
    except Exception as e:
        logger.error(f"Qualification error: {e}")
        return APIResponse(
            success=False,
            message="Qualification failed",
            error=str(e)
        )


@app.get("/api/search")
async def search_properties(
    location: str = Query(..., description="Property location"),
    property_type: str = Query("residential", description="residential or commercial"),
    topology: Optional[str] = Query(None, description="BHK or subtype"),
    budget_min: Optional[int] = Query(None, description="Min budget in INR"),
    budget_max: Optional[int] = Query(None, description="Max budget in INR"),
    project_status: Optional[str] = Query(None, description="Launching soon, New Launch, Under Construction, Ready to move in"),
    possession: Optional[str] = Query(None, description="3 Months, 6 Months, 1 year, 2+ years, Ready To Move")
):
    """
    Search for properties on realtyassistant.in.
    
    Returns property count and sample listings.
    """
    global _property_searcher
    
    if not _property_searcher:
        raise HTTPException(status_code=503, detail="Property searcher not initialized")
    
    try:
        result = await _property_searcher.search(
            location=location,
            property_type=property_type,
            topology=topology,
            budget_min=budget_min,
            budget_max=budget_max,
            project_status=project_status,
            possession=possession
        )
        
        return {
            "success": result.success,
            "count": result.count,
            "properties": result.properties[:5],  # Limit to 5
            "query_params": result.query_params,
            "source_url": result.source_url,
            "error": result.error
        }
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# Import database
from core.database import get_database, Lead as DbLead
from pydantic import BaseModel


class LeadCreateRequest(BaseModel):
    """Request model for creating a lead."""
    session_id: str
    timestamp: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    consent: bool = False
    location: Optional[str] = None
    property_category: Optional[str] = None
    property_type: Optional[str] = None
    bedroom: Optional[str] = None
    project_status: Optional[str] = None
    possession: Optional[str] = None
    budget: Optional[str] = None
    properties_found: int = 0
    search_url: Optional[str] = None
    qualified: bool = False


@app.post("/api/leads", status_code=201)
async def create_lead(lead_data: LeadCreateRequest):
    """Create or update a lead in the database."""
    try:
        db = get_database()
        lead = db.create_lead(lead_data.model_dump())
        return {
            "success": True,
            "message": "Lead saved successfully",
            "lead_id": lead.id if hasattr(lead, 'id') else None,
            "session_id": lead_data.session_id
        }
    except Exception as e:
        logger.error(f"Error saving lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/leads")
async def get_leads(
    qualified_only: bool = Query(False, description="Only return qualified leads"),
    limit: int = Query(100, description="Max leads to return"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get all leads from the database."""
    try:
        db = get_database()
        leads = db.get_all_leads(qualified_only=qualified_only, limit=limit, offset=offset)
        total = db.get_leads_count(qualified_only=qualified_only)
        
        return {
            "leads": leads,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error getting leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/leads/{session_id}")
async def get_lead_details(session_id: str):
    """Get lead details by session ID."""
    try:
        db = get_database()
        lead = db.get_lead(session_id)
        
        if lead:
            return lead.to_dict()
        
        raise HTTPException(status_code=404, detail="Lead not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/transcripts/{session_id}")
async def get_transcript(session_id: str):
    """Get conversation transcript by session ID."""
    logs_dir = Path(os.getenv("LOGS_DIR", "data/logs"))
    
    for file_path in logs_dir.glob(f"*{session_id}*_transcript.txt"):
        try:
            with open(file_path) as f:
                return {"transcript": f.read()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=404, detail="Transcript not found")


# Email request model
from pydantic import BaseModel, EmailStr
from typing import Dict, Any

class EmailSummaryRequest(BaseModel):
    to: str
    cc: str = "support@dmj.one"
    subject: str
    lead: Dict[str, Any]
    searchUrl: str = ""


@app.post("/api/send-summary-email")
async def send_summary_email(request: EmailSummaryRequest, background_tasks: BackgroundTasks):
    """
    Send email summary to user and support.
    Uses Python's built-in smtplib (no paid services).
    """
    background_tasks.add_task(send_email_async, request)
    return {"success": True, "message": "Email queued for sending"}


async def send_email_async(request: EmailSummaryRequest):
    """Send email using SMTP (Gmail, or local SMTP server)."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    # SMTP Configuration (using environment variables)
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@realtyassistant.in")
    
    # Build email content
    lead = request.lead
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f8fafc; padding: 20px; border: 1px solid #e2e8f0; }}
            .summary-item {{ padding: 10px 0; border-bottom: 1px solid #e2e8f0; }}
            .label {{ font-weight: bold; color: #64748b; }}
            .value {{ color: #1e293b; }}
            .cta {{ background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; margin-top: 15px; }}
            .footer {{ text-align: center; padding: 20px; color: #64748b; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">🏠 RealtyAssistant</h1>
                <p style="margin: 5px 0 0 0;">Your Property Search Summary</p>
            </div>
            <div class="content">
                <h2>Hello {lead.get('name', 'there')}!</h2>
                <p>Thank you for using RealtyAssistant! Here's a summary of your property search:</p>
                
                <div class="summary-item">
                    <span class="label">Name:</span> 
                    <span class="value">{lead.get('contact_name') or lead.get('name', 'Not provided')}</span>
                </div>
                <div class="summary-item">
                    <span class="label">Phone:</span> 
                    <span class="value">{lead.get('phone', 'Not provided')}</span>
                </div>
                <div class="summary-item">
                    <span class="label">Email:</span> 
                    <span class="value">{lead.get('email', 'Not provided')}</span>
                </div>
                <div class="summary-item">
                    <span class="label">Location:</span> 
                    <span class="value">{lead.get('location', 'Not specified')}</span>
                </div>
                <div class="summary-item">
                    <span class="label">Category:</span> 
                    <span class="value">{lead.get('property_category', 'Not specified')}</span>
                </div>
                <div class="summary-item">
                    <span class="label">Type:</span> 
                    <span class="value">{lead.get('property_type', 'Not specified')}</span>
                </div>
                <div class="summary-item">
                    <span class="label">Configuration:</span> 
                    <span class="value">{lead.get('bedroom') or lead.get('topology', 'Not specified')}</span>
                </div>
                
                <p style="margin-top: 20px;">
                    <a href="{request.searchUrl}" class="cta">🔍 Browse Matching Properties</a>
                </p>
                
                <p style="margin-top: 20px; font-size: 14px; color: #64748b;">
                    Our property experts will contact you soon with personalized recommendations!
                </p>
            </div>
            <div class="footer">
                <p>Powered by RealtyAssistant | dmj.one</p>
                <p>This is an automated email. Please do not reply directly.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text fallback
    text_content = f"""
    RealtyAssistant - Property Search Summary
    
    Hello {lead.get('name', 'there')}!
    
    Thank you for using RealtyAssistant! Here's your search summary:
    
    Name: {lead.get('contact_name') or lead.get('name', 'Not provided')}
    Phone: {lead.get('phone', 'Not provided')}
    Email: {lead.get('email', 'Not provided')}
    Location: {lead.get('location', 'Not specified')}
    Category: {lead.get('property_category', 'Not specified')}
    Type: {lead.get('property_type', 'Not specified')}
    Configuration: {lead.get('bedroom') or lead.get('topology', 'Not specified')}
    
    Browse matching properties: {request.searchUrl}
    
    Our property experts will contact you soon!
    
    ---
    Powered by RealtyAssistant | dmj.one
    """
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = request.subject
        msg['From'] = smtp_from
        msg['To'] = request.to
        msg['Cc'] = request.cc
        
        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        recipients = [request.to]
        if request.cc:
            recipients.append(request.cc)
        
        if smtp_user and smtp_password:
            # Use authenticated SMTP (e.g., Gmail)
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, recipients, msg.as_string())
            logger.info(f"Email sent to {request.to} and {request.cc}")
        else:
            # Log email for development (no SMTP configured)
            logger.info(f"Email would be sent to: {request.to}, CC: {request.cc}")
            logger.info(f"Subject: {request.subject}")
            
            # Save email to file for development
            email_log_path = Path("data/emails")
            email_log_path.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(email_log_path / f"{timestamp}_{request.to.replace('@', '_')}.html", "w") as f:
                f.write(html_content)
            
            logger.info(f"Email saved to data/emails/ for development")
            
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        # Save to queue for retry
        email_queue_path = Path("data/email_queue")
        email_queue_path.mkdir(parents=True, exist_ok=True)
        
        import json
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(email_queue_path / f"{timestamp}_email.json", "w") as f:
            json.dump({
                "to": request.to,
                "cc": request.cc,
                "subject": request.subject,
                "lead": request.lead,
                "searchUrl": request.searchUrl,
                "error": str(e)
            }, f, indent=2)


# =============================================================================
# Twilio/VAPI Webhook Endpoints and Call Initiation
# =============================================================================

@app.post("/api/initiate-call")
async def initiate_outbound_call(request: APILeadRequest, background_tasks: BackgroundTasks):
    """
    Initiate an outbound voice call to a lead.
    
    This endpoint triggers a call via Twilio or VAPI.ai based on configuration.
    """
    import os
    
    # Get provider from config
    provider = os.getenv("VOICE_PROVIDER", "twilio").lower()
    
    if provider == "twilio":
        return await initiate_twilio_call(request.lead)
    elif provider == "vapi":
        return await initiate_vapi_call(request.lead)
    else:
        return {"success": False, "error": f"Unknown voice provider: {provider}"}


async def initiate_twilio_call(lead: LeadInput):
    """
    Initiate an outbound call using Twilio.
    
    Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER
    to be set in environment variables.
    """
    import os
    
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
    webhook_url = os.getenv("WEBHOOK_BASE_URL", "http://localhost:9876")
    
    if not all([account_sid, auth_token, twilio_number]):
        return {
            "success": False,
            "error": "Twilio credentials not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER",
            "fallback": "Use chat mode or configure Twilio"
        }
    
    try:
        # Import Twilio client
        from twilio.rest import Client
        
        client = Client(account_sid, auth_token)
        
        # Create outbound call
        call = client.calls.create(
            to=lead.phone,
            from_=twilio_number,
            url=f"{webhook_url}/webhooks/twilio/voice?lead_name={lead.name}",
            status_callback=f"{webhook_url}/webhooks/twilio/status",
            record=True  # Enable recording for transcript
        )
        
        logger.info(f"Twilio call initiated: {call.sid} to {lead.phone}")
        
        return {
            "success": True,
            "provider": "twilio",
            "call_sid": call.sid,
            "status": call.status,
            "lead": lead.name,
            "phone": lead.phone
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "twilio package not installed. Run: pip install twilio",
        }
    except Exception as e:
        logger.error(f"Twilio call error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def initiate_vapi_call(lead: LeadInput):
    """
    Initiate an outbound call using VAPI.ai.
    
    Requires VAPI_API_KEY and VAPI_ASSISTANT_ID to be set.
    """
    import os
    import httpx
    
    api_key = os.getenv("VAPI_API_KEY")
    assistant_id = os.getenv("VAPI_ASSISTANT_ID")
    
    if not api_key:
        return {
            "success": False,
            "error": "VAPI credentials not configured. Set VAPI_API_KEY",
            "fallback": "Use chat mode or configure VAPI"
        }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.vapi.ai/call",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "assistantId": assistant_id,
                    "phoneNumber": lead.phone,
                    "customerName": lead.name,
                    "metadata": {
                        "lead_name": lead.name,
                        "lead_email": lead.email,
                        "lead_phone": lead.phone
                    }
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"VAPI call initiated: {data.get('id')} to {lead.phone}")
                return {
                    "success": True,
                    "provider": "vapi",
                    "call_id": data.get("id"),
                    "status": data.get("status"),
                    "lead": lead.name
                }
            else:
                return {
                    "success": False,
                    "error": f"VAPI error: {response.status_code} - {response.text}"
                }
                
    except Exception as e:
        logger.error(f"VAPI call error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/webhooks/twilio/voice")
async def twilio_voice_webhook(
    background_tasks: BackgroundTasks,
    lead_name: str = Query("Customer", description="Lead name")
):
    """
    Twilio voice webhook endpoint.
    
    This endpoint handles incoming Twilio voice callbacks and returns TwiML
    to conduct the qualification conversation.
    """
    from fastapi.responses import Response
    
    # Generate TwiML for the initial greeting
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" timeout="5" speechTimeout="auto" action="/webhooks/twilio/process?stage=greeting&amp;lead_name={lead_name}">
        <Say voice="Polly.Joanna">
            Hello, this is Realty Assistant calling about your property enquiry. Am I speaking with {lead_name}?
        </Say>
    </Gather>
    <Say voice="Polly.Joanna">We didn't receive any input. We'll try again later. Goodbye!</Say>
</Response>'''
    
    return Response(content=twiml, media_type="application/xml")


@app.post("/webhooks/twilio/process")
async def twilio_process_webhook(
    background_tasks: BackgroundTasks,
    stage: str = Query("greeting"),
    lead_name: str = Query("Customer"),
    SpeechResult: str = Query(None, description="Transcribed speech from Twilio")
):
    """
    Process Twilio speech input and continue the conversation flow.
    """
    from fastapi.responses import Response
    
    speech = SpeechResult or ""
    logger.info(f"Twilio stage={stage}, speech={speech}")
    
    # Define conversation flow stages
    stages = {
        "greeting": {
            "next": "location",
            "question": "Great! Which location are you searching for property in?"
        },
        "location": {
            "next": "property_type",
            "question": "Are you looking for a Residential or Commercial property?"
        },
        "property_type": {
            "next": "topology",
            "question": "How many bedrooms are you looking for? 1 BHK, 2 BHK, 3 BHK, or 4 BHK?"
        },
        "topology": {
            "next": "budget",
            "question": "What is your budget for this property?"
        },
        "budget": {
            "next": "consent",
            "question": "Would you like a sales representative to call you to discuss? Say yes or no."
        },
        "consent": {
            "next": "closing",
            "question": None
        }
    }
    
    current = stages.get(stage, {})
    next_stage = current.get("next", "closing")
    question = current.get("question")
    
    if next_stage == "closing" or stage == "consent":
        # Final closing
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">
        Thank you, {lead_name}! Based on your requirements, we'll have a representative contact you shortly with matching properties. Have a great day!
    </Say>
    <Hangup/>
</Response>'''
    else:
        # Continue conversation
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" timeout="5" speechTimeout="auto" action="/webhooks/twilio/process?stage={next_stage}&amp;lead_name={lead_name}">
        <Say voice="Polly.Joanna">{question}</Say>
    </Gather>
    <Say voice="Polly.Joanna">I didn't catch that. Let me transfer you to an agent.</Say>
</Response>'''
    
    return Response(content=twiml, media_type="application/xml")


@app.post("/webhooks/twilio/status")
async def twilio_status_webhook():
    """Handle Twilio call status updates."""
    return {"status": "received"}


@app.post("/webhooks/vapi/call")
async def vapi_call_webhook(background_tasks: BackgroundTasks):
    """
    VAPI.ai call webhook endpoint.
    
    This endpoint handles incoming VAPI call events like transcripts and call status.
    """
    # Placeholder for VAPI integration - VAPI handles conversation automatically
    return {
        "message": "VAPI webhook received",
        "documentation": "https://docs.vapi.ai"
    }


# =============================================================================
# CLI Functions
# =============================================================================

async def run_interactive_cli():
    """Run interactive CLI mode."""
    from agent import run_qualification_cli
    await run_qualification_cli()


async def run_simulation(
    name: str = "Test User",
    phone: str = "9876543210",
    email: str = None
):
    """Run a simulated qualification."""
    global _agent, _llm_engine, _property_searcher
    
    console.print(Panel.fit(
        "[bold blue]RealtyAssistant AI Agent[/bold blue]\n"
        "[dim]Simulated Lead Qualification[/dim]",
        border_style="blue"
    ))
    
    # Initialize components
    _llm_engine = LLMEngine()
    _property_searcher = PropertySearcher(headless=True)
    _agent = QualificationAgent(
        llm_engine=_llm_engine,
        property_searcher=_property_searcher
    )
    
    await _llm_engine.initialize()
    
    # Create lead
    lead = LeadInput(name=name, phone=phone, email=email)
    
    console.print(f"\n[green]Starting qualification for:[/green] {lead.name}")
    console.print(f"[dim]Phone:[/dim] {lead.phone}")
    console.print("-" * 40)
    
    # Run qualification
    summary = await _agent.qualify_lead(lead, mode="chat")
    
    # Display results
    console.print("\n" + "=" * 50)
    status_color = "green" if summary.status == QualificationStatus.QUALIFIED else "red"
    console.print(f"[bold {status_color}]STATUS: {summary.status.value.upper()}[/bold {status_color}]")
    console.print(f"[dim]Reason:[/dim] {summary.reason.summary}")
    console.print(f"[dim]Properties Found:[/dim] {summary.collected_data.property_count}")
    console.print(f"[dim]Duration:[/dim] {summary.duration_seconds:.1f}s")
    console.print("=" * 50)
    
    # Cleanup
    await _property_searcher.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="RealtyAssistant AI Agent for Lead Qualification"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Server command
    server_parser = subparsers.add_parser("serve", help="Start API server")
    server_parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind"
    )
    server_parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind"
    )
    server_parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload"
    )
    
    # Interactive CLI command
    cli_parser = subparsers.add_parser("cli", help="Run interactive CLI")
    
    # Simulation command
    sim_parser = subparsers.add_parser("simulate", help="Run simulation")
    sim_parser.add_argument("--name", default="Test User", help="Lead name")
    sim_parser.add_argument("--phone", default="9876543210", help="Phone number")
    sim_parser.add_argument("--email", default=None, help="Email address")
    
    args = parser.parse_args()
    
    if args.command == "serve":
        console.print(Panel.fit(
            "[bold blue]RealtyAssistant AI Agent[/bold blue]\n"
            f"[dim]Starting server on {args.host}:{args.port}[/dim]",
            border_style="blue"
        ))
        
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            reload=args.reload
        )
        
    elif args.command == "cli":
        asyncio.run(run_interactive_cli())
        
    elif args.command == "simulate":
        asyncio.run(run_simulation(
            name=args.name,
            phone=args.phone,
            email=args.email
        ))
        
    else:
        # Default: start server
        console.print(Panel.fit(
            "[bold blue]RealtyAssistant AI Agent[/bold blue]\n"
            "[dim]Starting server on 0.0.0.0:8000[/dim]\n\n"
            "[yellow]Usage:[/yellow]\n"
            "  python main.py serve    - Start API server\n"
            "  python main.py cli      - Interactive CLI\n"
            "  python main.py simulate - Run simulation",
            border_style="blue"
        ))
        
        uvicorn.run(
            "main:app",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            reload=os.getenv("DEBUG", "false").lower() == "true"
        )


if __name__ == "__main__":
    main()
