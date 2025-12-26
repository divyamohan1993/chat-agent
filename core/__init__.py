# =============================================================================
# RealtyAssistant AI Agent - Core Module
# =============================================================================
"""
Core components for the RealtyAssistant AI Voice/Chat Agent.

Modules:
- whisper_engine: Local speech-to-text using faster-whisper
- llm_engine: Local LLM with Gemini fallback
- fallback: Gemini API integration
- search_scout: realtyassistant.in web scraper
"""

from .whisper_engine import WhisperEngine
from .llm_engine import LLMEngine
from .fallback import GeminiFallback
from .search_scout import PropertySearcher

__all__ = [
    "WhisperEngine",
    "LLMEngine", 
    "GeminiFallback",
    "PropertySearcher"
]
