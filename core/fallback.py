# =============================================================================
# RealtyAssistant AI Agent - Gemini Fallback Engine
# =============================================================================
"""
Google Gemini API integration for fallback LLM inference.
Used when local LLM latency exceeds the threshold or fails.
"""

import os
import asyncio
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GeminiResponse:
    """Response from Gemini API."""
    text: str
    tokens_used: int
    latency_ms: float
    success: bool
    error: Optional[str] = None


class GeminiFallback:
    """
    Gemini API fallback for when local LLM is unavailable or slow.
    
    Features:
    - Async API calls for non-blocking operation
    - Automatic retry with exponential backoff
    - Context preservation from local LLM
    - Token counting and usage tracking
    """
    
    SUPPORTED_MODELS = [
        "gemini-2.0-flash-exp",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b", 
        "gemini-1.5-pro"
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.0-flash-exp",
        max_retries: int = 3
    ):
        """
        Initialize the Gemini fallback engine.
        
        Args:
            api_key: Gemini API key (or from env GEMINI_API_KEY)
            model_name: Model to use for inference
            max_retries: Maximum retry attempts
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.max_retries = max_retries
        self.model = None
        self._initialized = False
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set - fallback will be unavailable")
    
    def initialize(self) -> bool:
        """
        Initialize the Gemini client.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True
            
        if not self.api_key:
            logger.error("Cannot initialize Gemini - no API key")
            return False
            
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 1024,
                }
            )
            
            self._initialized = True
            logger.info(f"Gemini fallback initialized with model: {self.model_name}")
            return True
            
        except ImportError as e:
            logger.error(f"google-generativeai not installed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> GeminiResponse:
        """
        Generate a response using Gemini API.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            conversation_history: Previous conversation turns
            
        Returns:
            GeminiResponse with the generated text
        """
        import time
        start_time = time.time()
        
        if not self._initialized:
            if not self.initialize():
                return GeminiResponse(
                    text="",
                    tokens_used=0,
                    latency_ms=0,
                    success=False,
                    error="Gemini not initialized"
                )
        
        try:
            # Build the full prompt
            full_prompt = self._build_prompt(prompt, system_prompt, conversation_history)
            
            # Generate with retry logic
            response = await self._generate_with_retry(full_prompt)
            
            latency_ms = (time.time() - start_time) * 1000
            
            return GeminiResponse(
                text=response.text,
                tokens_used=self._count_tokens(response.text),
                latency_ms=latency_ms,
                success=True
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Gemini generation error: {e}")
            return GeminiResponse(
                text="",
                tokens_used=0,
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    def generate_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> GeminiResponse:
        """
        Synchronous version of generate for non-async contexts.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            conversation_history: Previous conversation turns
            
        Returns:
            GeminiResponse with the generated text
        """
        import time
        start_time = time.time()
        
        if not self._initialized:
            if not self.initialize():
                return GeminiResponse(
                    text="",
                    tokens_used=0,
                    latency_ms=0,
                    success=False,
                    error="Gemini not initialized"
                )
        
        try:
            full_prompt = self._build_prompt(prompt, system_prompt, conversation_history)
            
            response = self.model.generate_content(full_prompt)
            
            latency_ms = (time.time() - start_time) * 1000
            
            return GeminiResponse(
                text=response.text,
                tokens_used=self._count_tokens(response.text),
                latency_ms=latency_ms,
                success=True
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Gemini sync generation error: {e}")
            return GeminiResponse(
                text="",
                tokens_used=0,
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    async def _generate_with_retry(self, prompt: str) -> Any:
        """
        Generate with exponential backoff retry.
        
        Args:
            prompt: The full prompt to send
            
        Returns:
            Gemini response object
        """
        from tenacity import (
            retry,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception_type
        )
        
        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(Exception)
        )
        async def _call_api():
            # Run in executor since google-generativeai is not fully async
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(prompt)
            )
        
        return await _call_api()
    
    def _build_prompt(
        self,
        prompt: str,
        system_prompt: Optional[str],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> str:
        """
        Build the full prompt with context.
        
        Args:
            prompt: Current user prompt
            system_prompt: System instructions
            conversation_history: Previous turns
            
        Returns:
            Complete prompt string
        """
        parts = []
        
        if system_prompt:
            parts.append(f"System: {system_prompt}\n")
        
        if conversation_history:
            for turn in conversation_history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                parts.append(f"{role.capitalize()}: {content}")
        
        parts.append(f"User: {prompt}")
        parts.append("Assistant:")
        
        return "\n".join(parts)
    
    def _count_tokens(self, text: str) -> int:
        """
        Estimate token count for a text string.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated token count
        """
        # Rough estimation: ~4 chars per token
        return len(text) // 4
    
    def is_available(self) -> bool:
        """Check if Gemini fallback is available."""
        return bool(self.api_key) and self._check_import()
    
    def _check_import(self) -> bool:
        """Check if google-generativeai is installed."""
        try:
            import google.generativeai
            return True
        except ImportError:
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the fallback engine."""
        return {
            "model": self.model_name,
            "api_key_set": bool(self.api_key),
            "initialized": self._initialized,
            "available": self.is_available()
        }


# Singleton instance
_gemini_instance: Optional[GeminiFallback] = None


def get_gemini_fallback(
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash-exp"
) -> GeminiFallback:
    """
    Get or create a singleton GeminiFallback instance.
    
    Args:
        api_key: API key (only used on first call)
        model_name: Model name (only used on first call)
        
    Returns:
        GeminiFallback instance
    """
    global _gemini_instance
    
    if _gemini_instance is None:
        _gemini_instance = GeminiFallback(
            api_key=api_key,
            model_name=model_name
        )
    
    return _gemini_instance
