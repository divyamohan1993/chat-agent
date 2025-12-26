# =============================================================================
# RealtyAssistant AI Agent - Data Models
# =============================================================================
"""
Pydantic models for data validation and serialization.
Ensures strict schema compliance for all inputs and outputs.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, EmailStr


class PropertyType(str, Enum):
    """Property type enumeration."""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"


class ResidentialTopology(str, Enum):
    """Residential property topology."""
    BHK_1 = "1bhk"
    BHK_2 = "2bhk"
    BHK_3 = "3bhk"
    BHK_4 = "4bhk"


class CommercialSubtype(str, Enum):
    """Commercial property subtypes."""
    SHOP = "shop"
    OFFICE = "office"
    PLOT = "plot"


class ConversationStage(str, Enum):
    """Stages of the qualification conversation."""
    GREETING = "greeting"
    LOCATION = "location"
    PROPERTY_TYPE = "property_type"
    TOPOLOGY = "topology"
    BUDGET = "budget"
    CONSENT = "consent"
    SEARCH = "search"
    CLOSING = "closing"
    COMPLETED = "completed"


class QualificationStatus(str, Enum):
    """Lead qualification status."""
    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"
    PENDING = "pending"


class LeadInput(BaseModel):
    """Input lead record for qualification."""
    name: str = Field(..., min_length=1, description="Lead's name")
    phone: str = Field(..., min_length=10, description="Phone number")
    email: Optional[EmailStr] = Field(None, description="Email address")
    source: Optional[str] = Field("web", description="Lead source")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate and clean phone number."""
        # Remove non-digits
        cleaned = ''.join(c for c in v if c.isdigit())
        if len(cleaned) < 10:
            raise ValueError('Phone number must have at least 10 digits')
        return cleaned


class CollectedData(BaseModel):
    """Data collected during the conversation."""
    contact_name: Optional[str] = None
    location: Optional[str] = None
    property_category: Optional[str] = None  # Residential Properties / Commercial Properties
    property_type: Optional[str] = None      # Apartments, Shops, etc.
    bedroom: Optional[str] = None            # 1 BHK, Studio, etc.
    # Old fields kept for compatibility or internal mapping
    topology: Optional[str] = None
    budget_raw: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    sales_consent: Optional[bool] = None
    property_count: int = 0
    
    def is_complete(self) -> bool:
        """Check if all required data is collected."""
        return all([
            self.contact_name,
            self.location,
            self.property_category,
            self.property_type,
            # bedroom is optional for commercial
            self.sales_consent is not None
        ])
    
    def is_budget_numeric(self) -> bool:
        """Check if budget was successfully parsed to numeric."""
        return self.budget_min is not None or self.budget_max is not None


class ConversationTurn(BaseModel):
    """Single turn in the conversation."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: Optional[ConversationStage] = None
    extracted_data: Optional[Dict[str, Any]] = None


class ConversationSession(BaseModel):
    """Full conversation session."""
    session_id: str = Field(..., description="Unique session identifier")
    lead: LeadInput = Field(..., description="Original lead input")
    turns: List[ConversationTurn] = Field(default_factory=list)
    current_stage: ConversationStage = ConversationStage.GREETING
    collected_data: CollectedData = Field(default_factory=CollectedData)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    mode: str = Field("chat", description="'voice' or 'chat'")
    
    def add_turn(
        self,
        role: str,
        content: str,
        stage: Optional[ConversationStage] = None,
        extracted_data: Optional[Dict[str, Any]] = None
    ):
        """Add a conversation turn."""
        self.turns.append(ConversationTurn(
            role=role,
            content=content,
            stage=stage or self.current_stage,
            extracted_data=extracted_data
        ))
    
    def get_transcript(self) -> str:
        """Get the full conversation transcript."""
        lines = []
        for turn in self.turns:
            role_label = "Agent" if turn.role == "assistant" else "User"
            lines.append(f"[{role_label}]: {turn.content}")
        return "\n".join(lines)


class QualificationReason(BaseModel):
    """Detailed reasoning for qualification decision."""
    property_count_check: bool = Field(..., description="Properties found > 0")
    consent_check: bool = Field(..., description="Sales consent given")
    summary: str = Field(..., description="Human-readable summary")
    # budget check removed


class QualificationSummary(BaseModel):
    """Final qualification summary with all details."""
    session_id: str
    lead: LeadInput
    collected_data: CollectedData
    status: QualificationStatus
    reason: QualificationReason
    property_search_url: Optional[str] = None
    conversation_turns: int
    duration_seconds: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @classmethod
    def from_session(
        cls,
        session: ConversationSession,
        status: QualificationStatus,
        reason: QualificationReason,
        search_url: Optional[str] = None
    ) -> "QualificationSummary":
        """Create summary from a conversation session."""
        duration = 0.0
        if session.ended_at:
            duration = (session.ended_at - session.started_at).total_seconds()
        
        return cls(
            session_id=session.session_id,
            lead=session.lead,
            collected_data=session.collected_data,
            status=status,
            reason=reason,
            property_search_url=search_url,
            conversation_turns=len(session.turns),
            duration_seconds=duration
        )


class APILeadRequest(BaseModel):
    """API request to trigger lead qualification."""
    lead: LeadInput
    collected_data: Optional[Dict[str, Any]] = None  # Added to allow submitting pre-collected data
    mode: str = Field("chat", description="'voice' or 'chat'")
    simulate: bool = Field(True, description="Simulate conversation for testing")


class APIResponse(BaseModel):
    """Standard API response."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
