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
    
    # Conversation flow - mirrors chat widget with natural intro
    CONVERSATION_FLOW = {
        'greeting': {
            'question': "Hello! This is RealtyAssistant calling. Am I speaking with {name}?",
            'field': 'name_confirmed',
            'next': 'interest_check'
        },
        'interest_check': {
            'question': "Are you currently interested in purchasing or renting a property?",
            'field': 'interested',
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
        'verify_requirements': {
            'question': "Did I get your requirements right?",
            'field': 'verified',
            'next': 'search_complete'
        },
        'search_complete': {
            'question': "Excellent! I'm searching for matching properties now. Would you like our property expert to call you with personalized recommendations?",
            'field': 'consent',
            'next': None  # Dynamic
        },
        'ask_name': {
            'question': "By the way, may I know your good name so our expert knows who to ask for?",
            'field': 'name',
            'next': 'budget'
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
    
    def __init__(self, llm_engine=None, property_searcher=None):
        """Initialize voice handler with engines."""
        self.llm_engine = llm_engine
        self.property_searcher = property_searcher
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
    
    async def _enhance_with_llm(self, session: VoiceSession, user_input: str, base_response: str, context: str = "") -> str:
        """
        Optionally enhance response using LLM for more natural conversation.
        
        Falls back to base_response if LLM is unavailable or fails.
        """
        if not self.llm_engine:
            return base_response
        
        try:
            # Build conversation context
            history = session.conversation_history[-4:] if session.conversation_history else []
            history_text = "\n".join([f"{h['role']}: {h['content']}" for h in history])
            
            prompt = f"""You are a friendly real estate assistant on a phone call. 
Make this response sound more natural and human-like for a voice call.
Keep it short (1-2 sentences max) and conversational.

Context: {context}
Conversation so far:
{history_text}
User just said: "{user_input}"

Base response to deliver: {base_response}

Rewrite this naturally (keep the same meaning, just make it sound more human):"""

            enhanced = await self.llm_engine.generate(prompt, max_tokens=100)
            
            if enhanced and len(enhanced) > 10:
                return enhanced.strip()
            return base_response
            
        except Exception as e:
            logger.debug(f"LLM enhancement failed: {e}")
            return base_response
    
    async def _interpret_unclear_input(self, session: VoiceSession, user_input: str, expected_type: str) -> str:
        """
        Use LLM to interpret unclear or garbled input.
        
        Args:
            session: Current voice session
            user_input: The unclear transcription
            expected_type: What we expected (e.g., "city name", "yes or no", "number of bedrooms")
            
        Returns:
            Interpreted value or None if can't interpret
        """
        if not self.llm_engine:
            return None
        
        try:
            prompt = f"""You are helping interpret a voice transcription from a phone call.
The transcription might have accents or mispronunciations.

Expected type of answer: {expected_type}
Transcription: "{user_input}"

What did the user most likely mean? Give just the interpreted value, nothing else.
If you can't determine, say "UNCLEAR".

Examples:
- "noyda" for city → Noida
- "too bhk" for bedrooms → 2 BHK
- "yess please" for yes/no → yes

Your interpretation:"""

            result = await self.llm_engine.generate(prompt, max_tokens=50)
            
            if result and "UNCLEAR" not in result.upper():
                return result.strip()
            return None
            
        except Exception as e:
            logger.debug(f"LLM interpretation failed: {e}")
            return None

    async def _extract_requirements_from_speech(self, speech: str) -> Dict[str, Any]:
        """
        Extract all property requirements from natural speech using LLM.
        
        Handles statements like:
        - "I'm looking for a 3 BHK apartment in Noida under 50 lakhs"
        - "I want commercial space in Mumbai for my office"
        - "Need a 2 bedroom flat in Bangalore, budget around 1 crore"
        
        Returns dict with extracted fields (may be partial):
        - location, property_category, property_type, bedroom, budget, name
        """
        if not self.llm_engine or not speech or len(speech.strip()) < 5:
            return {}
        
        try:
            prompt = f"""Extract property search requirements from this customer statement.
Return ONLY a JSON object with these fields (use null for missing info):

Fields to extract:
- location: City name in India (e.g., Noida, Mumbai, Delhi, Bangalore)
- property_category: "Residential" or "Commercial"  
- property_type: Apartment/Flat, Villa/House, Plot, Office, Shop, etc.
- bedroom: Number of bedrooms (e.g., "2 BHK", "3 BHK")
- budget: Budget amount (e.g., "50 Lakhs", "1 Crore", "80 Lakhs to 1 Crore")
- name: Customer's name if they mentioned it
- timeline: When they want to buy (e.g., "immediately", "3 months", "6 months")
- purpose: "investment", "self-use", "rental", etc.

Customer said: "{speech}"

Return ONLY valid JSON, no other text:"""

            result = await self.llm_engine.generate(prompt, max_tokens=200)
            
            if result:
                # Clean up response - extract JSON
                result = result.strip()
                # Handle markdown code blocks
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0]
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0]
                
                import json
                try:
                    extracted = json.loads(result.strip())
                    # Clean null values
                    return {k: v for k, v in extracted.items() if v is not None and v != "null" and v != ""}
                except json.JSONDecodeError:
                    logger.debug(f"Failed to parse LLM JSON: {result}")
                    return {}
            
            return {}
            
        except Exception as e:
            logger.debug(f"Requirement extraction failed: {e}")
            return {}
    
    def _format_requirements_summary(self, data: Dict[str, Any]) -> str:
        """Format extracted requirements into a natural confirmation message."""
        parts = []
        
        if data.get('bedroom'):
            parts.append(f"a {data['bedroom']}")
        
        if data.get('property_type'):
            parts.append(data['property_type'].lower())
        elif data.get('property_category'):
            if 'commercial' in data['property_category'].lower():
                parts.append("commercial property")
            else:
                parts.append("property")
        
        if data.get('location'):
            parts.append(f"in {data['location']}")
        
        if data.get('budget'):
            parts.append(f"with a budget of {data['budget']}")
        
        if data.get('purpose'):
            parts.append(f"for {data['purpose']}")
        
        if parts:
            return " ".join(parts)
        return "a property"

    
    async def process_speech(
        self,
        session_id: str,
        speech_text: str,
        lead_name: str = "Customer",
        lead_phone: str = ""
    ) -> VoiceResponse:
        """
        Process speech input and generate response.
        
        Features:
        - Detects rich input with multiple requirements
        - Extracts all info using LLM
        - Jumps to verification if enough info collected
        - Falls back to stage-by-stage flow for simple answers
        """
        session = self.get_session(session_id)
        speech_text = speech_text.strip() if speech_text else ""
        
        logger.info(f"[Voice] Session {session_id}, Stage: {session.current_stage}, Input: '{speech_text}'")
        
        # Initialize from lead info (but use generic until we know real name)
        if 'phone' not in session.collected_data and lead_phone:
            session.collected_data['phone'] = lead_phone
        
        # Add to conversation history
        if speech_text:
            session.conversation_history.append({
                'role': 'user',
                'content': speech_text
            })
        
        # Check if this is rich input with multiple requirements (longer than 15 words or has property keywords)
        words = speech_text.lower().split() if speech_text else []
        property_keywords = ['bhk', 'bedroom', 'flat', 'apartment', 'villa', 'house', 'plot', 
                           'office', 'shop', 'lakh', 'crore', 'budget', 'noida', 'mumbai', 
                           'delhi', 'bangalore', 'pune', 'gurugram', 'looking', 'want', 'need']
        
        has_property_keywords = sum(1 for kw in property_keywords if kw in speech_text.lower()) >= 2
        is_rich_input = len(words) > 10 or has_property_keywords
        
        # Try to extract requirements from rich input
        if is_rich_input and session.current_stage in ['interest_check', 'location', 'property_category', 'property_type', 'bedroom']:
            extracted = await self._extract_requirements_from_speech(speech_text)
            
            if extracted and len(extracted) >= 2:
                logger.info(f"Extracted requirements: {extracted}")
                
                # Store extracted data
                for key in ['location', 'property_category', 'property_type', 'bedroom', 'budget', 'timeline', 'purpose']:
                    if extracted.get(key):
                        session.collected_data[key] = extracted[key]
                
                # If customer mentioned their name, use it
                if extracted.get('name'):
                    session.collected_data['name'] = extracted['name']
                    session.collected_data['name_confirmed'] = True
                
                # Generate confirmation message
                summary = self._format_requirements_summary(extracted)
                session.collected_data['requirements_extracted'] = True
                
                # Move to verification stage
                response = VoiceResponse(
                    message=f"Got it! So you're looking for {summary}. Did I get that right?",
                    next_stage='verify_requirements',
                    options=['Yes', 'No, let me correct'],
                    confidence=0.85
                )
                
                session.conversation_history.append({
                    'role': 'assistant',
                    'content': response.message
                })
                session.current_stage = response.next_stage
                
                return response
        
        # Process based on current stage (normal flow)
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
        elif stage == 'interest_check':
            return self._handle_interest_check(session, speech)
        elif stage == 'location':
            return await self._handle_location(session, speech)
        elif stage == 'property_category':
            return self._handle_category(session, speech)
        elif stage == 'property_type':
            return await self._handle_property_type(session, speech)
        elif stage == 'bedroom':
            return await self._handle_bedroom(session, speech)
        elif stage == 'verify_requirements':
            return await self._handle_verify_requirements(session, speech)
        elif stage == 'search_complete':
            return await self._handle_search_complete(session, speech)
        elif stage == 'ask_name':
            return self._handle_ask_name(session, speech)
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

    async def _perform_search_and_format(self, session: VoiceSession) -> str:
        """Perform search and format results for speech."""
        if not self.property_searcher:
            return "I have noted your requirements. Would you like our property expert to call you with personalized recommendations?"

        location = session.collected_data.get('location', '')
        category = session.collected_data.get('property_category', '')
        p_type = session.collected_data.get('property_type', '')
        bedroom = session.collected_data.get('bedroom', '')
        
        # Map category to 1 (Resi) or 4 (Comm) logic if needed, but searcher handles text
        # Clean up bedroom for searcher (extract standard BHK)
        topology = bedroom if bedroom else None
        
        logger.info(f"Voice Search: loc={location}, type={p_type}, bed={bedroom}")
        
        results = await self.property_searcher.search(
            location=location,
            property_type=category,
            topology=topology
        )
        
        if results.success and results.count > 0:
            # Store results
            session.collected_data['search_results'] = results.properties
            
            # Format speech
            top_props = results.properties[:2] # Speak top 2
            prop_names = ", ".join([p.get('title', 'Property') for p in top_props])
            
            speech = f"I found {results.count} properties in {location} matching your criteria. The top ones are {prop_names}. Would you like to talk to our expert for more details?"
            return speech
        else:
            return f"I looked for properties in {location} but didn't find exact matches right now. However, I can have our expert find off-market deals for you. Would you like a call back?"

    def _handle_greeting(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """
        Handle greeting stage - confirm identity and introduce service.
        
        Flow:
        1. Confirm if speaking with correct person
        2. If no, ask for name and update
        3. For new users, introduce RealtyAssistant
        4. Ask if interested in purchasing property
        """
        name = session.collected_data.get('name', 'there')
        is_name_confirmed = session.collected_data.get('name_confirmed', False)
        awaiting_name = session.collected_data.get('awaiting_name', False)
        introduced = session.collected_data.get('introduced', False)
        
        # If we're waiting for user's name after they said "no"
        if awaiting_name:
            # User provided their name
            if speech and len(speech.strip()) > 1:
                # Extract name from speech (could be "My name is John" or just "John")
                name_text = speech.strip()
                # Clean common prefixes
                for prefix in ["my name is", "this is", "i am", "i'm", "call me"]:
                    if name_text.lower().startswith(prefix):
                        name_text = name_text[len(prefix):].strip()
                
                session.collected_data['name'] = name_text.title()
                session.collected_data['awaiting_name'] = False
                session.collected_data['name_confirmed'] = True
                
                # Introduce RealtyAssistant and ask about interest
                intro = f"Nice to meet you, {name_text.title()}! "
                intro += "I'm calling from RealtyAssistant. We help people find their perfect property - "
                intro += "whether it's a dream home, an investment property, or commercial space. "
                intro += "Are you currently looking to purchase or rent any property?"
                
                session.collected_data['introduced'] = True
                
                return VoiceResponse(
                    message=intro,
                    next_stage='interest_check',
                    options=['Yes', 'No'],
                    confidence=0.9
                )
            else:
                return VoiceResponse(
                    message="I didn't catch that. Could you please tell me your name?",
                    next_stage='greeting',
                    confidence=0.5
                )
        
        # Check for affirmative/negative response
        consent, confidence = self._match_consent(speech)
        
        if consent is True or confidence > 0.5:
            # User confirmed their identity
            session.collected_data['name_confirmed'] = True
            
            if not introduced:
                # First time - introduce RealtyAssistant
                intro = f"Wonderful, {name}! I'm calling from RealtyAssistant. "
                intro += "We specialize in helping people find their ideal property across India. "
                intro += "Are you currently interested in purchasing or renting a property?"
                
                session.collected_data['introduced'] = True
                
                return VoiceResponse(
                    message=intro,
                    next_stage='interest_check',
                    options=['Yes, I am', 'Not right now'],
                    confidence=confidence
                )
            else:
                # Already introduced, proceed to location
                return VoiceResponse(
                    message=f"Great! Which city are you looking for property in?",
                    next_stage='location',
                    confidence=confidence
                )
                
        elif consent is False:
            # Wrong person - ask for their actual name
            session.collected_data['awaiting_name'] = True
            return VoiceResponse(
                message="Oh, I apologize! May I know who I'm speaking with?",
                next_stage='greeting',  # Stay on greeting to capture name
                confidence=0.8
            )
        else:
            # Unclear response - might be their name if we just asked
            # Or they might have said something unrelated
            if speech and len(speech.strip()) > 2:
                # Could be their name or a greeting like "hello" "hi"
                speech_lower = speech.lower().strip()
                greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']
                
                if any(g in speech_lower for g in greetings):
                    # They greeted back - confirm name again
                    return VoiceResponse(
                        message=f"Hello! Am I speaking with {name}?",
                        next_stage='greeting',
                        options=['Yes', 'No'],
                        confidence=0.7
                    )
                else:
                    # Assume they said yes and continue
                    session.collected_data['name_confirmed'] = True
                    session.collected_data['introduced'] = True
                    
                    return VoiceResponse(
                        message=f"Great! I'm from RealtyAssistant, and I'd love to help you find the perfect property. Which city are you looking in?",
                        next_stage='location',
                        confidence=0.6
                    )
            else:
                # Very short/empty - ask again
                return VoiceResponse(
                    message=f"I didn't quite catch that. Am I speaking with {name}?",
                    next_stage='greeting',
                    options=['Yes', 'No'],
                    confidence=0.5
                )
    
    def _handle_interest_check(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """
        Handle interest check stage - ask if user is interested in property.
        
        If yes: proceed to location
        If no: end call politely
        """
        consent, confidence = self._match_consent(speech)
        
        if consent is True:
            session.collected_data['interested'] = True
            name = session.collected_data.get('name', 'there')
            return VoiceResponse(
                message=f"Excellent, {name}! I'd love to help you find the perfect property. Which city are you looking in?",
                next_stage='location',
                options=['Noida', 'Mumbai', 'Delhi', 'Bangalore', 'Pune'],
                confidence=confidence
            )
        elif consent is False:
            session.collected_data['interested'] = False
            name = session.collected_data.get('name', 'there')
            return VoiceResponse(
                message=f"No worries, {name}! I completely understand. If you ever need help finding a property, feel free to reach out to RealtyAssistant. We're here to help. Have a wonderful day!",
                next_stage='thank_you',
                is_complete=True,
                collected_data=session.collected_data,
                confidence=confidence
            )
        else:
            # Unclear - check for property-related keywords that indicate interest
            speech_lower = speech.lower() if speech else ""
            interest_keywords = ['looking', 'searching', 'want', 'need', 'buy', 'rent', 'property', 'flat', 'apartment', 'house', 'villa']
            
            if any(kw in speech_lower for kw in interest_keywords):
                session.collected_data['interested'] = True
                return VoiceResponse(
                    message="Great! Which city are you interested in?",
                    next_stage='location',
                    confidence=0.6
                )
            else:
                # Ask again
                return VoiceResponse(
                    message="I just wanted to check - are you currently looking for a property to buy or rent?",
                    next_stage='interest_check',
                    options=['Yes', 'No'],
                    confidence=0.5
                )
    
    async def _handle_location(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle location stage with fuzzy city matching and LLM fallback."""
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
            # Try LLM interpretation for unclear city names
            interpreted = await self._interpret_unclear_input(
                session,
                speech,
                "Indian city name (e.g., Noida, Mumbai, Delhi, Bangalore, Pune, Gurugram, Lucknow)"
            )
            
            if interpreted:
                # Re-match with the interpreted value
                city, confidence = self._match_city(interpreted)
                if city and confidence >= 0.5:
                    session.collected_data['location'] = city
                    logger.info(f"LLM interpreted '{speech}' as '{city}'")
                    return VoiceResponse(
                        message=f"Got it! {city} it is. Are you looking for a Residential or Commercial property?",
                        next_stage='property_category',
                        options=['Residential', 'Commercial'],
                        confidence=0.7
                    )
                else:
                    # Use interpreted value directly
                    session.collected_data['location'] = interpreted.title()
                    return VoiceResponse(
                        message=f"I'll search for properties in {interpreted}. Are you looking for Residential or Commercial?",
                        next_stage='property_category',
                        options=['Residential', 'Commercial'],
                        confidence=0.6
                    )
            
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
    
    async def _handle_property_type(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle property type selection."""
        category = session.collected_data.get('property_category', 'Residential Properties')
        ptype, confidence = self._match_property_type(speech, category)
        
        session.collected_data['property_type'] = ptype
        
        if 'commercial' in category.lower():
            # Commercial flow ends here -> Search
            search_speech = await self._perform_search_and_format(session)
            
            return VoiceResponse(
                message=search_speech,
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
    
    async def _handle_bedroom(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle bedroom selection with LLM fallback for unclear transcriptions."""
        bedroom, confidence = self._match_bedroom(speech)
        
        if bedroom and confidence >= 0.5:
            session.collected_data['bedroom'] = bedroom
        else:
            # Try LLM interpretation for unclear speech (e.g., "3B edge game" -> "3 BHK")
            interpreted = await self._interpret_unclear_input(
                session, 
                speech, 
                "number of bedrooms (like 1 BHK, 2 BHK, 3 BHK, 4 BHK)"
            )
            
            if interpreted:
                # Try to extract BHK from LLM response
                bhk_match = re.search(r'(\d+)\s*(?:bhk|bk|bedroom)?', interpreted.lower())
                if bhk_match:
                    bedroom = f"{bhk_match.group(1)} BHK"
                    session.collected_data['bedroom'] = bedroom
                    confidence = 0.7
                    logger.info(f"LLM interpreted '{speech}' as '{bedroom}'")
                else:
                    session.collected_data['bedroom'] = '2 BHK'
                    confidence = 0.5
            else:
                # Default to 2 BHK if can't determine
                session.collected_data['bedroom'] = '2 BHK'
                confidence = 0.5
        
        # Residential flow ends here -> Search
        search_speech = await self._perform_search_and_format(session)
        
        return VoiceResponse(
            message=search_speech,
            next_stage='search_complete',
            options=['Yes, call me', 'No thanks'],
            confidence=confidence
        )
    
    async def _handle_verify_requirements(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle verification of extracted requirements."""
        consent, confidence = self._match_consent(speech)
        
        if consent is True:
            # Requirements confirmed - perform search
            session.collected_data['verified'] = True
            search_speech = await self._perform_search_and_format(session)
            
            return VoiceResponse(
                message=search_speech,
                next_stage='search_complete',
                options=['Yes, call me', 'No thanks'],
                confidence=confidence
            )
        elif consent is False:
            # User wants to correct - ask what's wrong
            return VoiceResponse(
                message="No problem! Please tell me what you're looking for - the city, property type, bedrooms, budget - anything you'd like.",
                next_stage='location',  # Reset to location for a fresh start
                confidence=0.8
            )
        else:
            # Unclear - assume confirmed and proceed
            session.collected_data['verified'] = True
            search_speech = await self._perform_search_and_format(session)
            
            return VoiceResponse(
                message=f"I'll proceed with that. {search_speech}",
                next_stage='search_complete',
                options=['Yes', 'No'],
                confidence=0.6
            )
    
    async def _handle_search_complete(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle post-search consent for callback - asks for name if not known."""
        consent, confidence = self._match_consent(speech)
        
        # Check if we know the user's real name
        name = session.collected_data.get('name', '')
        name_confirmed = session.collected_data.get('name_confirmed', False)
        has_real_name = name_confirmed and name and name.lower() not in ['customer', 'there', '']
        
        if consent is True:
            session.collected_data['consent'] = True
            
            if not has_real_name:
                # Ask for name naturally before proceeding
                return VoiceResponse(
                    message="Wonderful! Before I connect you with our expert, may I know your good name?",
                    next_stage='ask_name',
                    confidence=confidence
                )
            else:
                # Already have name - ask for budget
                return VoiceResponse(
                    message=f"Great, {name}! What's your budget range for this property?",
                    next_stage='budget',
                    confidence=confidence
                )
                
        elif consent is False:
            session.collected_data['consent'] = False
            return VoiceResponse(
                message="No problem at all! Thank you for your time. If you ever need help finding a property, feel free to call RealtyAssistant. Have a wonderful day!",
                next_stage='thank_you',
                is_complete=True,
                collected_data=session.collected_data,
                confidence=confidence
            )
        else:
            # Unclear - check if they're asking about properties (wanting more info)
            speech_lower = speech.lower() if speech else ""
            info_keywords = ['tell', 'more', 'about', 'details', 'price', 'cost', 'where', 'which']
            
            if any(kw in speech_lower for kw in info_keywords):
                # They want more info
                location = session.collected_data.get('location', 'the area')
                return VoiceResponse(
                    message=f"I can share more details! We have several great options in {location}. Would you like our property expert to call you with detailed information and virtual tours?",
                    next_stage='search_complete',
                    options=['Yes', 'No'],
                    confidence=0.6
                )
            else:
                # Assume yes and ask for name
                session.collected_data['consent'] = True
                if not has_real_name:
                    return VoiceResponse(
                        message="I'll arrange a callback for you. May I have your name please?",
                        next_stage='ask_name',
                        confidence=0.5
                    )
                else:
                    return VoiceResponse(
                        message=f"Alright {name}! What's your budget for this property?",
                        next_stage='budget',
                        confidence=0.5
                    )
    
    def _handle_ask_name(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Handle name collection in middle of conversation."""
        if speech and len(speech.strip()) > 1:
            # Extract name from speech
            name_text = speech.strip()
            
            # Clean common prefixes
            for prefix in ["my name is", "this is", "i am", "i'm", "call me", "it's", "its"]:
                if name_text.lower().startswith(prefix):
                    name_text = name_text[len(prefix):].strip()
            
            # Clean trailing pleasantries
            name_text = name_text.split(',')[0].strip()  # "John, nice to meet you" -> "John"
            
            session.collected_data['name'] = name_text.title()
            session.collected_data['name_confirmed'] = True
            
            return VoiceResponse(
                message=f"Nice to meet you, {name_text.title()}! What's your budget range for the property?",
                next_stage='budget',
                confidence=0.9
            )
        else:
            return VoiceResponse(
                message="I didn't catch your name. Could you please tell me your name?",
                next_stage='ask_name',
                confidence=0.5
            )
    
    def _handle_consent(self, session: VoiceSession, speech: str) -> VoiceResponse:
        """Legacy consent handler - redirects to search_complete."""
        # This is kept for backward compatibility
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
        """Handle email input and complete the call."""
        email = self._extract_email(speech)
        session.collected_data['email'] = email
        
        # Get the completion message directly
        name = session.collected_data.get('name', 'there')
        location = session.collected_data.get('location', 'your preferred area')
        phone = session.collected_data.get('phone', 'your number')
        bedroom = session.collected_data.get('bedroom', '')
        property_type = session.collected_data.get('property_type', '')
        
        # Create a natural, personalized farewell
        farewell = f"Thank you so much, {name}! I've saved all your preferences. "
        farewell += f"You're looking for a {bedroom} {property_type} in {location}. "
        farewell += f"Our property expert will call you shortly at {phone} with personalized recommendations. "
        farewell += "Have a wonderful day!"
        
        return VoiceResponse(
            message=farewell,
            next_stage='complete',
            is_complete=True,
            collected_data=session.collected_data,
            confidence=0.95
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


def get_voice_handler(llm_engine=None, property_searcher=None) -> VoiceHandler:
    """Get or create singleton VoiceHandler instance."""
    global _voice_handler
    
    if _voice_handler is None:
        _voice_handler = VoiceHandler(llm_engine=llm_engine, property_searcher=property_searcher)
    
    return _voice_handler
