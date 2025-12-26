# =============================================================================
# RealtyAssistant AI Agent - Qualification Agent
# =============================================================================
"""
Main qualification agent that orchestrates the entire lead qualification flow.
Implements the conversation script, data extraction, and qualification logic.
"""

import os
import re
import json
import uuid
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, Callable

from models import (
    LeadInput, ConversationSession, ConversationStage,
    CollectedData, QualificationStatus, QualificationReason,
    QualificationSummary, PropertyType, ConversationTurn
)
from core.llm_engine import LLMEngine, get_llm_engine
from core.search_scout import PropertySearcher, get_property_searcher

logger = logging.getLogger(__name__)


class QualificationAgent:
    """
    AI Agent for real estate lead qualification.
    
    Features:
    - Scripted conversation flow with LLM-based responses
    - Data extraction and validation
    - Property availability search
    - Deterministic qualification rules
    - Full transcript and JSON output persistence
    """
    
    def __init__(
        self,
        llm_engine: Optional[LLMEngine] = None,
        property_searcher: Optional[PropertySearcher] = None,
        logs_dir: str = "data/logs",
        leads_dir: str = "data/leads"
    ):
        """
        Initialize the qualification agent.
        
        Args:
            llm_engine: LLM engine for response generation
            property_searcher: Property search engine
            logs_dir: Directory for conversation logs
            leads_dir: Directory for qualification summaries
        """
        self.llm_engine = llm_engine or get_llm_engine()
        self.property_searcher = property_searcher or get_property_searcher()
        self.logs_dir = Path(logs_dir)
        self.leads_dir = Path(leads_dir)
        
        # Ensure directories exist
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.leads_dir.mkdir(parents=True, exist_ok=True)
        
        # Load prompt templates
        self._load_templates()
        
        self._initialized = False
    
    def _load_templates(self):
        """Load conversation templates from file."""
        template_path = Path("prompts/conversation_templates.json")
        
        if template_path.exists():
            with open(template_path) as f:
                self.templates = json.load(f)
        else:
            # Default templates
            self.templates = {
                "greeting": {
                    "initial": "Hello — this is RealtyAssistant calling about the enquiry you submitted. Am I speaking with {lead_name}?",
                    "name_mismatch": "May I know your name?",
                    "name_confirmed": "Great, {contact_name}! Thank you for confirming."
                },
                "location": {
                    "ask": "Which location are you searching in?",
                    "acknowledge": "Got it, {location} is a wonderful area."
                },
                "property_type": {
                    "ask": "Are you looking for a Residential or Commercial property?",
                    "residential_ack": "Residential property it is!",
                    "commercial_ack": "Commercial property — understood!"
                },
                "topology": {
                    "residential_ask": "Which BHK configuration would you prefer: 1 BHK, 2 BHK, 3 BHK, or 4 BHK?",
                    "commercial_ask": "What type of commercial space: Shop, Office, or Commercial Plot?",
                    "acknowledge": "Perfect, {topology} noted."
                },
                "budget": {
                    "ask": "What is your budget for this property?",
                    "acknowledge": "Thank you, I've noted your budget as {budget}."
                },
                "consent": {
                    "ask": "Would you like a sales representative to call you to discuss? (Yes/No)",
                    "yes_response": "Wonderful! A representative will reach out soon.",
                    "no_response": "No problem. We'll keep your information on file."
                },
                "closing": {
                    "qualified": "Thanks {contact_name}! Based on your inputs, we found {property_count} matching properties. A representative will call you shortly. Have a great day!",
                    "not_qualified": "Thanks for your time, {contact_name}. We'll keep you posted when matching properties become available. Have a great day!"
                }
            }
    
    async def initialize(self) -> bool:
        """
        Initialize all components.
        
        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True
        
        # Initialize LLM engine
        await self.llm_engine.initialize()
        
        # Initialize property searcher
        await self.property_searcher.initialize()
        
        self._initialized = True
        logger.info("Qualification agent initialized")
        return True
    
    async def qualify_lead(
        self,
        lead: LeadInput,
        mode: str = "chat",
        user_input_handler: Optional[Callable[[str], str]] = None
    ) -> QualificationSummary:
        """
        Run the full qualification flow for a lead.
        
        Args:
            lead: Input lead record
            mode: "voice" or "chat"
            user_input_handler: Function to get user input (for interactive mode)
            
        Returns:
            QualificationSummary with the final result
        """
        await self.initialize()
        
        # Create session
        session = ConversationSession(
            session_id=str(uuid.uuid4()),
            lead=lead,
            mode=mode,
            collected_data=CollectedData(contact_name=lead.name)
        )
        
        logger.info(f"Starting qualification for lead: {lead.name} ({session.session_id})")
        
        try:
            # Run conversation stages
            await self._run_greeting(session, user_input_handler)
            await self._run_location(session, user_input_handler)
            await self._run_property_type(session, user_input_handler)
            await self._run_topology(session, user_input_handler)
            await self._run_budget(session, user_input_handler)
            await self._run_consent(session, user_input_handler)
            await self._run_search(session)
            
            # Apply qualification rules
            status, reason, search_url = self._evaluate_qualification(session)
            
            # Generate closing message
            await self._run_closing(session, status)
            
            # Mark session complete
            session.current_stage = ConversationStage.COMPLETED
            session.ended_at = datetime.now(timezone.utc)
            
            # Create summary
            summary = QualificationSummary.from_session(
                session, status, reason, search_url
            )
            
            # Persist data
            await self._persist_session(session, summary)
            
            logger.info(f"Qualification complete: {status.value}")
            return summary
            
        except Exception as e:
            logger.error(f"Qualification error: {e}")
            session.ended_at = datetime.now(timezone.utc)
            
            # Create error summary
            reason = QualificationReason(
                property_count_check=False,
                consent_check=False,
                budget_parsed_check=False,
                summary=f"Error during qualification: {str(e)}"
            )
            
            summary = QualificationSummary.from_session(
                session, QualificationStatus.NOT_QUALIFIED, reason
            )
            
            await self._persist_session(session, summary)
            return summary
    
    async def _run_greeting(
        self,
        session: ConversationSession,
        user_input_handler: Optional[Callable]
    ):
        """Run the greeting stage."""
        session.current_stage = ConversationStage.GREETING
        
        # Initial greeting
        greeting = self.templates["greeting"]["initial"].format(
            lead_name=session.lead.name
        )
        session.add_turn("assistant", greeting)
        
        # Get user response
        user_response = await self._get_user_response(
            session, user_input_handler,
            f"Greeting response for {session.lead.name}"
        )
        session.add_turn("user", user_response)
        
        # Check if it's the right person
        is_correct_person = await self._check_name_confirmation(user_response, session.lead.name)
        
        if not is_correct_person:
            # Ask for name
            session.add_turn("assistant", self.templates["greeting"]["name_mismatch"])
            name_response = await self._get_user_response(
                session, user_input_handler, "Name"
            )
            session.add_turn("user", name_response)
            
            # Extract name from response
            extracted_name = await self._extract_name(name_response)
            session.collected_data.contact_name = extracted_name or name_response.strip()
        else:
            session.collected_data.contact_name = session.lead.name
        
        # Confirm name
        confirmation = self.templates["greeting"]["name_confirmed"].format(
            contact_name=session.collected_data.contact_name
        )
        session.add_turn("assistant", confirmation)
    
    async def _run_location(
        self,
        session: ConversationSession,
        user_input_handler: Optional[Callable]
    ):
        """Run the location stage."""
        session.current_stage = ConversationStage.LOCATION
        
        # Ask for location
        session.add_turn("assistant", self.templates["location"]["ask"])
        
        # Get response
        user_response = await self._get_user_response(
            session, user_input_handler, "Location"
        )
        session.add_turn("user", user_response)
        
        # Extract and store location
        session.collected_data.location = user_response.strip()
        
        # Acknowledge
        ack = self.templates["location"]["acknowledge"].format(
            location=session.collected_data.location
        )
        session.add_turn("assistant", ack)
    
    async def _run_property_type(
        self,
        session: ConversationSession,
        user_input_handler: Optional[Callable]
    ):
        """Run the property type stage."""
        session.current_stage = ConversationStage.PROPERTY_TYPE
        
        # Ask for property type
        session.add_turn("assistant", self.templates["property_type"]["ask"])
        
        # Get response
        user_response = await self._get_user_response(
            session, user_input_handler, "Residential or Commercial"
        )
        session.add_turn("user", user_response)
        
        # Parse property type
        response_lower = user_response.lower()
        if "residential" in response_lower or "res" in response_lower:
            session.collected_data.property_type = PropertyType.RESIDENTIAL
            ack = self.templates["property_type"]["residential_ack"]
        elif "commercial" in response_lower or "comm" in response_lower:
            session.collected_data.property_type = PropertyType.COMMERCIAL
            ack = self.templates["property_type"]["commercial_ack"]
        else:
            # Default to residential
            session.collected_data.property_type = PropertyType.RESIDENTIAL
            ack = self.templates["property_type"]["residential_ack"]
        
        session.add_turn("assistant", ack)
    
    async def _run_topology(
        self,
        session: ConversationSession,
        user_input_handler: Optional[Callable]
    ):
        """Run the topology/subtype stage."""
        session.current_stage = ConversationStage.TOPOLOGY
        
        # Choose question based on property type
        if session.collected_data.property_type == PropertyType.RESIDENTIAL:
            question = self.templates["topology"]["residential_ask"]
        else:
            question = self.templates["topology"]["commercial_ask"]
        
        session.add_turn("assistant", question)
        
        # Get response
        user_response = await self._get_user_response(
            session, user_input_handler,
            "1BHK/2BHK/3BHK/4BHK" if session.collected_data.property_type == PropertyType.RESIDENTIAL else "Shop/Office/Plot"
        )
        session.add_turn("user", user_response)
        
        # Parse topology
        session.collected_data.topology = self._parse_topology(
            user_response, session.collected_data.property_type
        )
        
        # Acknowledge
        ack = self.templates["topology"]["acknowledge"].format(
            topology=session.collected_data.topology
        )
        session.add_turn("assistant", ack)
    
    async def _run_budget(
        self,
        session: ConversationSession,
        user_input_handler: Optional[Callable]
    ):
        """Run the budget stage."""
        session.current_stage = ConversationStage.BUDGET
        
        # Ask for budget
        session.add_turn("assistant", self.templates["budget"]["ask"])
        
        # Get response
        user_response = await self._get_user_response(
            session, user_input_handler, "Budget (e.g., 50 lakhs)"
        )
        session.add_turn("user", user_response)
        
        # Store raw budget
        session.collected_data.budget_raw = user_response.strip()
        
        # Parse to numeric
        budget_min, budget_max = PropertySearcher.parse_budget(user_response)
        session.collected_data.budget_min = budget_min
        session.collected_data.budget_max = budget_max
        
        # Acknowledge
        ack = self.templates["budget"]["acknowledge"].format(
            budget=session.collected_data.budget_raw
        )
        session.add_turn("assistant", ack)
    
    async def _run_consent(
        self,
        session: ConversationSession,
        user_input_handler: Optional[Callable]
    ):
        """Run the consent stage."""
        session.current_stage = ConversationStage.CONSENT
        
        # Ask for consent
        session.add_turn("assistant", self.templates["consent"]["ask"])
        
        # Get response
        user_response = await self._get_user_response(
            session, user_input_handler, "Yes or No"
        )
        session.add_turn("user", user_response)
        
        # Parse consent
        response_lower = user_response.lower().strip()
        session.collected_data.sales_consent = any(
            word in response_lower for word in ["yes", "yeah", "sure", "ok", "okay", "yep", "yup", "y"]
        )
        
        # Respond based on consent
        if session.collected_data.sales_consent:
            session.add_turn("assistant", self.templates["consent"]["yes_response"])
        else:
            session.add_turn("assistant", self.templates["consent"]["no_response"])
    
    async def _run_search(self, session: ConversationSession):
        """Run the property search."""
        session.current_stage = ConversationStage.SEARCH
        
        logger.info("Searching for matching properties...")
        
        # Perform search
        result = await self.property_searcher.search(
            location=session.collected_data.location or "",
            property_type=session.collected_data.property_type.value if session.collected_data.property_type else "residential",
            topology=session.collected_data.topology,
            budget_min=session.collected_data.budget_min,
            budget_max=session.collected_data.budget_max
        )
        
        # Store result
        session.collected_data.property_count = result.count
        
        logger.info(f"Found {result.count} matching properties")
    
    async def _run_closing(
        self,
        session: ConversationSession,
        status: QualificationStatus
    ):
        """Run the closing stage."""
        session.current_stage = ConversationStage.CLOSING
        
        # Generate closing message based on status
        if status == QualificationStatus.QUALIFIED:
            closing = self.templates["closing"]["qualified"].format(
                contact_name=session.collected_data.contact_name,
                property_count=session.collected_data.property_count
            )
        else:
            closing = self.templates["closing"]["not_qualified"].format(
                contact_name=session.collected_data.contact_name
            )
        
        session.add_turn("assistant", closing)
    
    def _evaluate_qualification(
        self,
        session: ConversationSession
    ) -> Tuple[QualificationStatus, QualificationReason, Optional[str]]:
        """
        Apply deterministic qualification rules.
        
        Returns:
            Tuple of (status, reason, search_url)
        """
        data = session.collected_data
        
        # Check conditions
        property_check = data.property_count > 0
        consent_check = data.sales_consent is True
        budget_check = data.is_budget_numeric()
        
        # Determine status
        if property_check and consent_check and budget_check:
            status = QualificationStatus.QUALIFIED
            summary = (
                f"Lead qualified: {data.property_count} properties found, "
                f"consent given, budget parsed successfully."
            )
        else:
            status = QualificationStatus.NOT_QUALIFIED
            reasons = []
            if not property_check:
                reasons.append("no matching properties found")
            if not consent_check:
                reasons.append("no sales consent")
            if not budget_check:
                reasons.append("budget could not be parsed")
            summary = f"Lead not qualified: {', '.join(reasons)}."
        
        reason = QualificationReason(
            property_count_check=property_check,
            consent_check=consent_check,
            budget_parsed_check=budget_check,
            summary=summary
        )
        
        # Build search URL
        search_url = self.property_searcher._build_search_url(
            location=data.location or "",
            property_type=data.property_type.value if data.property_type else "residential",
            topology=data.topology,
            budget_min=data.budget_min,
            budget_max=data.budget_max
        )
        
        return status, reason, search_url
    
    async def _persist_session(
        self,
        session: ConversationSession,
        summary: QualificationSummary
    ):
        """
        Persist conversation and summary to disk.
        
        Args:
            session: Conversation session
            summary: Qualification summary
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\-]', '_', session.lead.name)
        base_filename = f"{timestamp}_{safe_name}_{session.session_id[:8]}"
        
        # Save transcript
        transcript_path = self.logs_dir / f"{base_filename}_transcript.txt"
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(f"Session ID: {session.session_id}\n")
            f.write(f"Lead: {session.lead.name} ({session.lead.phone})\n")
            f.write(f"Mode: {session.mode}\n")
            f.write(f"Started: {session.started_at}\n")
            f.write(f"Ended: {session.ended_at}\n")
            f.write("=" * 50 + "\n\n")
            f.write(session.get_transcript())
        
        logger.info(f"Saved transcript: {transcript_path}")
        
        # Save summary JSON
        summary_path = self.leads_dir / f"{base_filename}_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary.model_dump(mode="json"), f, indent=2, default=str)
        
        logger.info(f"Saved summary: {summary_path}")
    
    async def _get_user_response(
        self,
        session: ConversationSession,
        user_input_handler: Optional[Callable],
        prompt_hint: str
    ) -> str:
        """
        Get user response via handler or simulation.
        
        Args:
            session: Current session
            user_input_handler: Optional input handler
            prompt_hint: Hint for simulation
            
        Returns:
            User response string
        """
        if user_input_handler:
            # Use provided handler (for interactive mode)
            return await asyncio.get_event_loop().run_in_executor(
                None, user_input_handler, prompt_hint
            )
        else:
            # Simulate response using LLM
            return await self._simulate_user_response(session, prompt_hint)
    
    async def _simulate_user_response(
        self,
        session: ConversationSession,
        prompt_hint: str
    ) -> str:
        """
        Simulate a realistic user response for testing.
        
        Args:
            session: Current session
            prompt_hint: What kind of response to generate
            
        Returns:
            Simulated response
        """
        system_prompt = (
            "You are simulating a real estate buyer responding to an agent. "
            "Give short, natural responses. Do not include any system text or role labels. "
            f"The buyer's name is {session.lead.name}."
        )
        
        # Build context from conversation
        history = []
        for turn in session.turns[-4:]:  # Last 4 turns for context
            history.append({
                "role": turn.role,
                "content": turn.content
            })
        
        prompt = f"Respond naturally to the agent. You should provide: {prompt_hint}"
        
        response = await self.llm_engine.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            conversation_history=history,
            temperature=0.8,
            max_tokens=50
        )
        
        if response.success:
            return response.text.strip()
        else:
            # Fallback simulated responses
            simulations = {
                "Greeting": "Yes, this is me.",
                "Name": session.lead.name,
                "Location": "Mumbai, Andheri West",
                "Residential or Commercial": "Residential",
                "1BHK/2BHK/3BHK/4BHK": "2 BHK",
                "Shop/Office/Plot": "Office space",
                "Budget": "50 to 60 lakhs",
                "Yes or No": "Yes"
            }
            
            for key, value in simulations.items():
                if key in prompt_hint:
                    return value
            
            return "Yes"
    
    async def _check_name_confirmation(
        self,
        response: str,
        expected_name: str
    ) -> bool:
        """
        Check if user confirmed they are the expected person.
        
        Args:
            response: User response
            expected_name: Expected name
            
        Returns:
            True if confirmed
        """
        response_lower = response.lower().strip()
        
        # Positive confirmations
        positive_words = ["yes", "yeah", "yep", "yup", "that's me", "speaking", "this is", "correct", "right"]
        
        for word in positive_words:
            if word in response_lower:
                return True
        
        # Check if they said the name
        if expected_name.lower() in response_lower:
            return True
        
        return False
    
    async def _extract_name(self, response: str) -> Optional[str]:
        """
        Extract name from user response.
        
        Args:
            response: User response
            
        Returns:
            Extracted name or None
        """
        # Clean common prefixes
        prefixes = ["my name is", "i am", "i'm", "this is", "call me"]
        
        response_lower = response.lower().strip()
        
        for prefix in prefixes:
            if prefix in response_lower:
                # Extract after prefix
                name = response_lower.split(prefix)[-1].strip()
                # Capitalize words
                return " ".join(word.capitalize() for word in name.split())
        
        # Just clean and return
        return " ".join(word.capitalize() for word in response.strip().split())
    
    def _parse_topology(self, response: str, property_type: PropertyType) -> str:
        """
        Parse topology from user response.
        
        Args:
            response: User response
            property_type: Property type
            
        Returns:
            Parsed topology string
        """
        response_lower = response.lower()
        
        if property_type == PropertyType.RESIDENTIAL:
            # Look for BHK
            bhk_match = re.search(r'(\d+)\s*bhk', response_lower)
            if bhk_match:
                return f"{bhk_match.group(1)} BHK"
            
            # Look for just numbers
            num_match = re.search(r'\b([1-4])\b', response_lower)
            if num_match:
                return f"{num_match.group(1)} BHK"
            
            return "2 BHK"  # Default
        else:
            # Commercial
            if "shop" in response_lower:
                return "Shop"
            elif "office" in response_lower:
                return "Office"
            elif "plot" in response_lower:
                return "Plot"
            else:
                return "Office"  # Default


# CLI function for direct execution
async def run_qualification_cli():
    """Run qualification from command line."""
    import sys
    
    print("\n" + "=" * 60)
    print("RealtyAssistant - AI Lead Qualification Agent")
    print("=" * 60 + "\n")
    
    # Get lead details
    name = input("Enter lead name: ").strip() or "John Doe"
    phone = input("Enter phone number: ").strip() or "9876543210"
    email = input("Enter email (optional): ").strip() or None
    
    lead = LeadInput(name=name, phone=phone, email=email)
    
    # Create agent and run
    agent = QualificationAgent()
    
    print("\n" + "-" * 40)
    print("Starting qualification flow...")
    print("-" * 40 + "\n")
    
    # Interactive input handler
    def get_input(prompt_hint: str) -> str:
        return input(f"[Your response - {prompt_hint}]: ").strip() or ""
    
    summary = await agent.qualify_lead(lead, mode="chat", user_input_handler=get_input)
    
    print("\n" + "=" * 60)
    print("QUALIFICATION RESULT")
    print("=" * 60)
    print(f"Status: {summary.status.value.upper()}")
    print(f"Reason: {summary.reason.summary}")
    print(f"Property Count: {summary.collected_data.property_count}")
    print(f"Duration: {summary.duration_seconds:.1f} seconds")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_qualification_cli())
