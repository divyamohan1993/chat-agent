# =============================================================================
# RealtyAssistant AI Agent - Voice Call Handler
# =============================================================================
"""
Handles voice call conversations with robust accent/mispronunciation handling.
Uses fuzzy matching, synonym mapping, and LLM fallback for understanding.
"""

import re
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from difflib import SequenceMatcher, get_close_matches
import unicodedata

logger = logging.getLogger(__name__)


@dataclass
class VoiceSession:
    """Voice call session state."""
    session_id: str
    current_stage: str = "greeting"
    collected_data: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2


@dataclass 
class VoiceResponse:
    """Response to send back to voice caller."""
    message: str
    next_stage: str
    options: Optional[List[str]] = None
    is_complete: bool = False
    collected_data: Optional[Dict[str, Any]] = None
    confidence: float = 1.0


class VoiceHandler:
    """
    Voice conversation handler with robust speech understanding.
    
    Features:
    - Fuzzy matching for location/city names with accent variations
    - Synonym mapping for common mispronunciations
    - LLM fallback for complex understanding
    - Same conversation flow as chat widget
    """
    
    # City names with common variations and mispronunciations
    CITY_VARIATIONS = {
        'noida': ['noida', 'noyda', 'noeda', 'naida', 'noda', 'nodia'],
        'greater noida': ['greater noida', 'greater noyda', 'big noida', 'greater naida', 'greaternoida'],
        'greater noida west': ['greater noida west', 'noida west', 'noida extension', 'gnw', 'gaur city'],
        'lucknow': ['lucknow', 'lakhnou', 'lakhnau', 'lucnow', 'luknow'],
        'gurugram': ['gurugram', 'gurgaon', 'gurugaon', 'ggn', 'gurgram', 'gurugraam'],
        'ghaziabad': ['ghaziabad', 'gaziabad', 'gzb', 'gaziyabad', 'ghaziabat'],
        'pune': ['pune', 'poona', 'puna', 'poone'],
        'thane': ['thane', 'thana', 'thaney', 'tane'],
        'mumbai': ['mumbai', 'bombay', 'mumbay', 'bambai', 'mumby'],
        'navi mumbai': ['navi mumbai', 'new mumbai', 'new bombay', 'navimumbai'],
        'dehradun': ['dehradun', 'dehradoon', 'dehra dun', 'dehradhun', 'doon'],
        'agra': ['agra', 'aagra', 'agara'],
        'vrindavan': ['vrindavan', 'brindavan', 'vrindaavan', 'vrundavan', 'mathura vrindavan'],
        'delhi': ['delhi', 'dilli', 'new delhi', 'deli', 'dehli'],
        'varanasi': ['varanasi', 'banaras', 'benares', 'kashi', 'varanashi'],
        'bengaluru': ['bengaluru', 'bangalore', 'banglore', 'bangaluru', 'blr'],
    }
    
    # Mumbai areas mapping
    MUMBAI_AREAS = [
        'andheri', 'bandra', 'malad', 'goregaon', 'powai', 'worli', 'borivali',
        'kandivali', 'juhu', 'khar', 'santacruz', 'versova', 'lokhandwala',
        'oshiwara', 'wadala', 'dadar', 'parel', 'lower parel', 'bkc', 'kurla',
        'ghatkopar', 'mulund', 'vikhroli', 'chembur', 'colaba', 'marine lines',
        'crawford market', 'churchgate', 'nariman point', 'fort', 'mahalaxmi'
    ]
    
    # Property category variations
    CATEGORY_VARIATIONS = {
        'residential': ['residential', 'resi', 'home', 'house', 'flat', 'apartment', 'living', 'stay', 'residence'],
        'commercial': ['commercial', 'office', 'shop', 'business', 'retail', 'store', 'workspace', 'work space']
    }
    
    # Property type variations (residential)
    PROPERTY_TYPE_RESIDENTIAL = {
        'apartments': ['apartment', 'flat', 'flats', 'appartment', 'appt', 'unit'],
        'villas': ['villa', 'bungalow', 'banglow', 'independent house', 'kothi', 'farmhouse'],
        'residential plots': ['plot', 'land', 'plat', 'residential plot', 'land plot'],
        'independent floor': ['floor', 'builder floor', 'independent floor', 'single floor'],
        'residential studio': ['studio', 'studio apartment', 'bachelor pad', 'single room'],
    }
    
    # Bedroom variations - handles accent issues
    BEDROOM_VARIATIONS = {
        '1 bhk': ['1 bhk', 'one bhk', '1bhk', 'one bedroom', '1 bedroom', 'single bhk', 'ek bhk', 'one bk', '1 bk'],
        '2 bhk': ['2 bhk', 'two bhk', '2bhk', 'two bedroom', '2 bedroom', 'do bhk', 'two bk', '2 bk', 'double bhk'],
        '3 bhk': ['3 bhk', 'three bhk', '3bhk', 'three bedroom', '3 bedroom', 'teen bhk', 'three bk', '3 bk', 'triple bhk'],
        '4 bhk': ['4 bhk', 'four bhk', '4bhk', 'four bedroom', '4 bedroom', 'char bhk', 'four bk', '4 bk', 'quad bhk'],
        '5 bhk': ['5 bhk', 'five bhk', '5bhk', 'five bedroom', '5 bedroom', 'paanch bhk', 'five bk', '5 bk'],
        'studio': ['studio', 'studio apartment', 'single room', 'bachelor', '1 room', 'one room', 'rk', '1rk'],
    }
    
    # Consent variations
    CONSENT_VARIATIONS = {
        'yes': ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'fine', 'alright', 'definitely', 
                'absolutely', 'please', 'go ahead', 'call me', 'contact me', 'haan', 'ji', 'thik hai'],
        'no': ['no', 'nope', 'nah', 'not now', 'later', 'dont', "don't", 'no thanks', 
               'not interested', 'nahi', 'na', 'mat karo', 'baad mein']
    }
    
    # Conversation flow - mirrors chat widget
    CONVERSATION_FLOW = {
        'greeting': {
            'question': "Hello! This is RealtyAssistant calling. Am I speaking with {name}?",
            'field': 'name_confirmed',
            'next': 'location'
        },
        'location': {
            'question': "Great! Which city are you looking for property in?",
            'field': 'location',
            'next': 'property_category'
        },
        'property_category': {
            'question': "Got it! Are you looking for a Residential or Commercial property?",
            'field': 'property_category',
            'next': 'property_type'
        },
        'property_type': {
            'question': None,  # Dynamic based on category
            'field': 'property_type',
            'next': 'bedroom'
        },
        'bedroom': {
            'question': "How many bedrooms do you need? 1 BHK, 2 BHK, 3 BHK, or 4 BHK?",
            'field': 'bedroom',
            'next': 'search_complete'
        },
        'search_complete': {
            'question': "Excellent! I'm searching for matching properties now. Would you like our property expert to call you with personalized recommendations?",
            'field': 'consent',
            'next': None  # Dynamic
        },
        'budget': {
            'question': "What's your budget range for this property?",
            'field': 'budget',
            'next': 'phone_confirm'
        },
        'phone_confirm': {
            'question': "I'll have an expert call you at this number. Can you also share your email for property alerts?",
            'field': 'email',
            'next': 'complete'
        },
        'complete': {
            'question': "Thank you! Our property expert will contact you shortly with matching properties in {location}. Have a wonderful day!",
            'field': None,
            'next': None
        },
        'thank_you': {
            'question': "No problem! Thank you for your interest. Feel free to call us anytime. Have a great day!",
            'field': None,
            'next': None
        }
    }
    
    def __init__(self, llm_engine=None):
        """Initialize voice handler with optional LLM engine for fallback."""
        self.llm_engine = llm_engine
        self.sessions: Dict[str, VoiceSession] = {}
        
        # Build reverse lookup for faster matching
        self._build_reverse_lookups()
    
    def _build_reverse_lookups(self):
        """Build reverse mapping for fast fuzzy matching."""
        self.city_lookup = {}
        for canonical, variations in self.CITY_VARIATIONS.items():
            for var in variations:
                self.city_lookup[var.lower()] = canonical
        
        self.bedroom_lookup = {}
        for canonical, variations in self.BEDROOM_VARIATIONS.items():
            for var in variations:
                self.bedroom_lookup[var.lower()] = canonical
        
        self.category_lookup = {}
        for canonical, variations in self.CATEGORY_VARIATIONS.items():
            for var in variations:
                self.category_lookup[var.lower()] = canonical
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching - handle accents and cleaning."""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower().strip()
        
        # Remove accents/diacritics
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(c for c in text if not unicodedata.combining(c))
        
        # Remove punctuation except spaces
        text = re.sub(r'[^\w\s]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _fuzzy_match(self, text: str, options: List[str], threshold: float = 0.6) -> Optional[str]:
        """Fuzzy match text against options with configurable threshold."""
        text = self._normalize_text(text)
        
        if not text:
            return None
        
        # Direct match first
        for opt in options:
            if self._normalize_text(opt) == text:
                return opt
        
        # Substring match
        for opt in options:
            opt_norm = self._normalize_text(opt)
            if text in opt_norm or opt_norm in text:
                return opt
        
        # Fuzzy match using SequenceMatcher
        best_match = None
        best_ratio = 0
        
        for opt in options:
            opt_norm = self._normalize_text(opt)
            ratio = SequenceMatcher(None, text, opt_norm).ratio()
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_match = opt
        
        return best_match
    
    def _match_city(self, speech: str) -> Tuple[Optional[str], float]:
        """Match spoken city name with confidence score."""
        speech_norm = self._normalize_text(speech)
        
        if not speech_norm:
            return None, 0.0
        
        # Check Mumbai areas first (map to Mumbai)
        for area in self.MUMBAI_AREAS:
            if area in speech_norm:
                logger.info(f"Matched Mumbai area: {area}")
                return 'mumbai', 0.9
        
        # Direct lookup in built mapping
        for var, canonical in self.city_lookup.items():
            if var in speech_norm:
                return canonical.title(), 0.95
        
        # Fuzzy match against all cities
        all_cities = list(self.CITY_VARIATIONS.keys())
        best_match = None
        best_score = 0.0
        
        for city in all_cities:
            for var in self.CITY_VARIATIONS[city]:
                var_norm = self._normalize_text(var)
                
                # Check if variation appears in speech
                if var_norm in speech_norm:
                    return city.title(), 0.95
                
                # Calculate similarity
                ratio = SequenceMatcher(None, var_norm, speech_norm).ratio()
                
                # Also check word-level similarity
                words = speech_norm.split()
                for word in words:
                    word_ratio = SequenceMatcher(None, var_norm, word).ratio()
                    ratio = max(ratio, word_ratio)
                
                if ratio > best_score:
                    best_score = ratio
                    best_match = city
        
        if best_score >= 0.6:
            return best_match.title(), best_score
        
        return None, 0.0
    
    def _match_bedroom(self, speech: str) -> Tuple[Optional[str], float]:
        """Match spoken bedroom requirement."""
        speech_norm = self._normalize_text(speech)
        
        # Check for numeric patterns first
        bhk_pattern = r'(\d+)\s*(?:bhk|bk|bedroom|bed)'
        match = re.search(bhk_pattern, speech_norm)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 5:
                return f'{num} BHK', 0.95
        
        # Check for word numbers
        word_nums = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
                     'ek': '1', 'do': '2', 'teen': '3', 'char': '4', 'paanch': '5'}
        for word, num in word_nums.items():
            if word in speech_norm and ('bhk' in speech_norm or 'bedroom' in speech_norm or 'bk' in speech_norm):
                return f'{num} BHK', 0.9
        
        # Direct lookup
        for var, canonical in self.bedroom_lookup.items():
            if var in speech_norm:
                return canonical.upper().replace(' BHK', ' BHK'), 0.9
        
        # Fuzzy match
        all_bedrooms = list(self.BEDROOM_VARIATIONS.keys())
        match = self._fuzzy_match(speech, all_bedrooms, threshold=0.5)
        if match:
            return match.upper().replace(' BHK', ' BHK'), 0.7
        
        return None, 0.0
    
    def _match_category(self, speech: str) -> Tuple[Optional[str], float]:
        """Match property category (residential/commercial)."""
        speech_norm = self._normalize_text(speech)
        
        # Direct lookup
        for var, canonical in self.category_lookup.items():
            if var in speech_norm:
                return f'{canonical.title()} Properties', 0.95
        
        # Fuzzy match
        if self._fuzzy_match(speech, self.CATEGORY_VARIATIONS['residential'], threshold=0.6):
            return 'Residential Properties', 0.8
        if self._fuzzy_match(speech, self.CATEGORY_VARIATIONS['commercial'], threshold=0.6):
            return 'Commercial Properties', 0.8
        
        return None, 0.0
    
    def _match_consent(self, speech: str) -> Tuple[Optional[bool], float]:
        """Match consent response (yes/no)."""
        speech_norm = self._normalize_text(speech)
        
        # Check for yes variations
        for var in self.CONSENT_VARIATIONS['yes']:
            if var in speech_norm:
                return True, 0.95
        
        # Check for no variations
        for var in self.CONSENT_VARIATIONS['no']:
            if var in speech_norm:
                return False, 0.95
        
        # Fuzzy match
        yes_match = self._fuzzy_match(speech, self.CONSENT_VARIATIONS['yes'], threshold=0.6)
        if yes_match:
            return True, 0.7
        
        no_match = self._fuzzy_match(speech, self.CONSENT_VARIATIONS['no'], threshold=0.6)
        if no_match:
            return False, 0.7
        
        return None, 0.0
    
    def _match_property_type(self, speech: str, category: str) -> Tuple[Optional[str], float]:
        """Match property type based on category."""
        speech_norm = self._normalize_text(speech)
        
        if 'commercial' in category.lower():
            types = ['Office Space', 'Shop', 'Commercial Plots', 'Showrooms', 'High Street Retail']
        else:
            types = ['Apartments', 'Villas', 'Residential Plots', 'Independent Floor', 'Residential Studio']
        
        # Direct match
        for ptype in types:
            if self._normalize_text(ptype) in speech_norm:
                return ptype, 0.95
        
        # Check variations for residential
        if 'residential' in category.lower():
            for canonical, variations in self.PROPERTY_TYPE_RESIDENTIAL.items():
                for var in variations:
                    if var in speech_norm:
                        return canonical.title(), 0.9
        
        # Fuzzy match
        match = self._fuzzy_match(speech, types, threshold=0.5)
        if match:
            return match, 0.7
        
        # Default based on common keywords
        if any(kw in speech_norm for kw in ['flat', 'apartment', 'building']):
            return 'Apartments', 0.6
        if any(kw in speech_norm for kw in ['house', 'kothi', 'bungalow']):
            return 'Villas', 0.6
        
        return 'Apartments', 0.5  # Default to apartments
    
    def _extract_budget(self, speech: str) -> Optional[str]:
        """Extract budget from speech."""
        speech_norm = self._normalize_text(speech)
        
        # Look for patterns like "50 lakhs", "1 crore", "1.5 cr"
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:lakh|lac|lacs|lakhs)',
            r'(\d+(?:\.\d+)?)\s*(?:crore|cr|crores)',
            r'around\s*(\d+(?:\.\d+)?)\s*(?:lakh|lac|crore|cr)',
            r'budget\s*(?:is|of)?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lac|crore|cr)?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, speech_norm)
            if match:
                value = match.group(1)
                if 'crore' in speech_norm or ' cr' in speech_norm:
                    return f"{value} Crore"
                else:
                    return f"{value} Lakhs"
        
        # Extract any mentioned number with lakhs/crore
        if 'crore' in speech_norm or ' cr ' in speech_norm:
            nums = re.findall(r'(\d+(?:\.\d+)?)', speech_norm)
            if nums:
                return f"{nums[0]} Crore"
        
        if 'lakh' in speech_norm or 'lac' in speech_norm:
            nums = re.findall(r'(\d+(?:\.\d+)?)', speech_norm)
            if nums:
                return f"{nums[0]} Lakhs"
        
        return speech  # Return as-is if can't parse
    
    def _extract_email(self, speech: str) -> Optional[str]:
        """Extract email from speech."""
        # Common email patterns in voice
        speech = speech.lower().strip()
        
        # Replace spoken words with symbols
        speech = speech.replace(' at ', '@')
        speech = speech.replace(' at the rate ', '@')
        speech = speech.replace(' at rate ', '@')
        speech = speech.replace(' dot ', '.')
        speech = speech.replace(' period ', '.')
        speech = speech.replace(' underscore ', '_')
        
        # Remove spaces around @ and .
        speech = re.sub(r'\s*@\s*', '@', speech)
        speech = re.sub(r'\s*\.\s*', '.', speech)
        
        # Look for email pattern
        email_pattern = r'[\w.+-]+@[\w.-]+\.\w+'
        match = re.search(email_pattern, speech)
        if match:
            return match.group(0)
        
        return speech  # Return cleaned version
    
    def get_session(self, session_id: str) -> VoiceSession:
        """Get or create voice session."""
        if session_id not in self.sessions:
            self.sessions[session_id] = VoiceSession(session_id=session_id)
        return self.sessions[session_id]
    
    async def process_speech(
        self,
        session_id: str,
        speech_text: str,
        lead_name: str = "Customer",
        lead_phone: str = ""
    ) -> VoiceResponse:
        """
        Process speech input and generate response.
        
        Args:
            session_id: Unique session identifier
            speech_text: Transcribed speech from caller
            lead_name: Name of the lead (from CRM/dialer)
            lead_phone: Phone number of the lead
            
        Returns:
            VoiceResponse with message and next stage
        """
        session = self.get_session(session_id)
        speech_text = speech_text.strip() if speech_text else ""
        
        logger.info(f"[Voice] Session {session_id}, Stage: {session.current_stage}, Input: '{speech_text}'")
        
        # Initialize name from lead info
        if 'name' not in session.collected_data and lead_name:
            session.collected_data['name'] = lead_name
        if 'phone' not in session.collected_data and lead_phone:
            session.collected_data['phone'] = lead_phone
        
        # Add to conversation history
        if speech_text:
            session.conversation_history.append({
                'role': 'user',
                'content': speech_text
            })
        
        # Process based on current stage
        response = await self._process_stage(session, speech_text)
        
        # Add response to history
        session.conversation_history.append({
            'role': 'assistant',
            'content': response.message
        })
        
        # Update session stage
        session.current_stage = response.next_stage
        
        return response
    
    async def _process_stage(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Process input based on current conversation stage."""
        stage = session.current_stage
        flow = self.CONVERSATION_FLOW.get(stage)
        
        if not flow:
            return self._create_error_response(session)
        
        # Handle each stage
        if stage == 'greeting':
            return self._handle_greeting(session, speech)
        elif stage == 'location':
            return self._handle_location(session, speech)
        elif stage == 'property_category':
            return self._handle_category(session, speech)
        elif stage == 'property_type':
            return self._handle_property_type(session, speech)
        elif stage == 'bedroom':
            return self._handle_bedroom(session, speech)
        elif stage == 'search_complete':
            return self._handle_consent(session, speech)
        elif stage == 'budget':
            return self._handle_budget(session, speech)
        elif stage == 'phone_confirm':
            return self._handle_email(session, speech)
        elif stage == 'complete':
            return self._handle_complete(session)
        elif stage == 'thank_you':
            return self._handle_thank_you(session)
        else:
            return self._create_error_response(session)
    
    def _handle_greeting(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle greeting stage - confirm identity."""
        name = session.collected_data.get('name', 'there')
        
        # Check for affirmative response
        consent, confidence = self._match_consent(speech)
        
        if consent is True or confidence > 0.5:
            session.collected_data['name_confirmed'] = True
            return VoiceResponse(
                message=f"Great to speak with you, {name}! I'm calling to help you find the perfect property. Which city are you looking for property in?",
                next_stage='location',
                confidence=confidence
            )
        elif consent is False:
            # They said no - might be wrong person
            return VoiceResponse(
                message="I apologize for the confusion. Could you please tell me your name?",
                next_stage='greeting',  # Stay on greeting
                confidence=0.7
            )
        else:
            # Assume they confirmed and continue
            session.collected_data['name_confirmed'] = True
            return VoiceResponse(
                message=f"I'll help you find the perfect property. Which city are you looking for property in?",
                next_stage='location',
                confidence=0.6
            )
    
    def _handle_location(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle location stage with fuzzy city matching."""
        city, confidence = self._match_city(speech)
        
        if city and confidence >= 0.6:
            session.collected_data['location'] = city
            return VoiceResponse(
                message=f"Great choice! {city} has some wonderful properties. Are you looking for a Residential or Commercial property?",
                next_stage='property_category',
                options=['Residential', 'Commercial'],
                confidence=confidence
            )
        else:
            session.retry_count += 1
            if session.retry_count > session.max_retries:
                # Use what they said as-is
                session.collected_data['location'] = speech.title() if speech else 'Not Specified'
                return VoiceResponse(
                    message=f"I'll note down {speech}. Are you looking for a Residential or Commercial property?",
                    next_stage='property_category',
                    confidence=0.5
                )
            
            return VoiceResponse(
                message="I didn't quite catch that. Could you please tell me the city name again? For example, Noida, Mumbai, Delhi, or Bangalore?",
                next_stage='location',
                options=['Noida', 'Mumbai', 'Delhi', 'Bangalore', 'Pune', 'Gurugram'],
                confidence=0.3
            )
    
    def _handle_category(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle property category selection."""
        category, confidence = self._match_category(speech)
        
        if category and confidence >= 0.5:
            session.collected_data['property_category'] = category
            
            if 'commercial' in category.lower():
                return VoiceResponse(
                    message="Commercial property it is! What type are you looking for? Office space, Shop, or Showroom?",
                    next_stage='property_type',
                    options=['Office Space', 'Shop', 'Showroom'],
                    confidence=confidence
                )
            else:
                return VoiceResponse(
                    message="Perfect! What type of residential property? Apartment, Villa, or Plot?",
                    next_stage='property_type',
                    options=['Apartment', 'Villa', 'Plot'],
                    confidence=confidence
                )
        else:
            session.retry_count += 1
            if session.retry_count > session.max_retries:
                session.collected_data['property_category'] = 'Residential Properties'
                return VoiceResponse(
                    message="I'll assume Residential. What type of property? Apartment, Villa, or Plot?",
                    next_stage='property_type',
                    confidence=0.5
                )
            
            return VoiceResponse(
                message="Would you like a Residential property like a flat or house? Or a Commercial property like a shop or office?",
                next_stage='property_category',
                options=['Residential', 'Commercial'],
                confidence=0.3
            )
    
    def _handle_property_type(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle property type selection."""
        category = session.collected_data.get('property_category', 'Residential Properties')
        ptype, confidence = self._match_property_type(speech, category)
        
        session.collected_data['property_type'] = ptype
        
        if 'commercial' in category.lower():
            return VoiceResponse(
                message=f"Got it, {ptype}! Now searching for matching properties. Would you like our expert to call you with personalized recommendations?",
                next_stage='search_complete',
                options=['Yes', 'No'],
                confidence=confidence
            )
        else:
            return VoiceResponse(
                message=f"Excellent, {ptype}! How many bedrooms do you need? 1 BHK, 2 BHK, 3 BHK, or 4 BHK?",
                next_stage='bedroom',
                options=['1 BHK', '2 BHK', '3 BHK', '4 BHK'],
                confidence=confidence
            )
    
    def _handle_bedroom(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle bedroom selection."""
        bedroom, confidence = self._match_bedroom(speech)
        
        if bedroom and confidence >= 0.5:
            session.collected_data['bedroom'] = bedroom
        else:
            # Default to what they said or 2 BHK
            session.collected_data['bedroom'] = '2 BHK'
            confidence = 0.5
        
        location = session.collected_data.get('location', 'your area')
        bedroom_display = session.collected_data.get('bedroom', '2 BHK')
        
        return VoiceResponse(
            message=f"Perfect! {bedroom_display} in {location}. I'm searching for matching properties now. Would you like our property expert to call you with personalized recommendations?",
            next_stage='search_complete',
            options=['Yes, call me', 'No thanks'],
            confidence=confidence
        )
    
    def _handle_consent(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle consent for sales call."""
        consent, confidence = self._match_consent(speech)
        
        if consent is True:
            session.collected_data['consent'] = True
            return VoiceResponse(
                message="Great! What's your budget range for this property?",
                next_stage='budget',
                confidence=confidence
            )
        elif consent is False:
            session.collected_data['consent'] = False
            return VoiceResponse(
                message="No problem! Thank you for your interest in RealtyAssistant. Feel free to call us anytime. Have a wonderful day!",
                next_stage='thank_you',
                is_complete=True,
                collected_data=session.collected_data,
                confidence=confidence
            )
        else:
            # Assume yes and continue
            session.collected_data['consent'] = True
            return VoiceResponse(
                message="I'll have our expert give you a call. What's your budget range?",
                next_stage='budget',
                confidence=0.5
            )
    
    def _handle_budget(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle budget input."""
        budget = self._extract_budget(speech)
        session.collected_data['budget'] = budget
        
        phone = session.collected_data.get('phone', 'this number')
        
        return VoiceResponse(
            message=f"Noted, budget of {budget}. Our expert will call you at {phone}. Can you share your email address for property alerts?",
            next_stage='phone_confirm',
            confidence=0.8
        )
    
    def _handle_email(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle email input."""
        email = self._extract_email(speech)
        session.collected_data['email'] = email
        
        return VoiceResponse(
            message="",  # Will be filled in complete handler
            next_stage='complete',
            confidence=0.8
        )
    
    def _handle_complete(self, session: VoiceSession) -> VoiceResponse:
        """Handle conversation completion."""
        name = session.collected_data.get('name', 'there')
        location = session.collected_data.get('location', 'your preferred area')
        phone = session.collected_data.get('phone', '')
        
        return VoiceResponse(
            message=f"Thank you, {name}! I've saved your preferences. Our property expert will call you at {phone} with matching properties in {location}. Have a wonderful day!",
            next_stage='complete',
            is_complete=True,
            collected_data=session.collected_data,
            confidence=1.0
        )
    
    def _handle_thank_you(self, session: VoiceSession) -> VoiceResponse:
        """Handle thank you (declined consent)."""
        return VoiceResponse(
            message="Thank you for your time! Feel free to call us back anytime. Goodbye!",
            next_stage='thank_you',
            is_complete=True,
            collected_data=session.collected_data,
            confidence=1.0
        )
    
    def _create_error_response(self, session: VoiceSession) -> VoiceResponse:
        """Create error/fallback response."""
        return VoiceResponse(
            message="I apologize, I'm having trouble understanding. Let me transfer you to a human agent. Please hold.",
            next_stage='error',
            is_complete=True,
            confidence=0.0
        )
    
    def get_initial_greeting(self, lead_name: str = "Customer") -> str:
        """Get the initial greeting for a new call."""
        return f"Hello! This is RealtyAssistant calling about your property enquiry. Am I speaking with {lead_name}?"
    
    def clear_session(self, session_id: str):
        """Clear a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]


# Singleton instance
_voice_handler: Optional[VoiceHandler] = None


def get_voice_handler(llm_engine=None) -> VoiceHandler:
    """Get or create singleton VoiceHandler instance."""
    global _voice_handler
    
    if _voice_handler is None:
        _voice_handler = VoiceHandler(llm_engine=llm_engine)
    
    return _voice_handler
