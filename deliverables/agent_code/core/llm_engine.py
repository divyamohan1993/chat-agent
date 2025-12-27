# =============================================================================
# RealtyAssistant AI Agent - LLM Engine with Hybrid Fallback
# =============================================================================
"""
Local LLM inference using Ollama with automatic Gemini fallback.
Implements latency monitoring and intelligent routing.
"""

import os
import time
import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .fallback import GeminiFallback, get_gemini_fallback

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Available LLM providers."""
    OLLAMA = "ollama"
    GEMINI = "gemini"
    NONE = "none"


@dataclass
class LLMResponse:
    """Response from the LLM engine."""
    text: str
    provider: LLMProvider
    latency_ms: float
    tokens_used: int
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMEngine:
    """
    Hybrid LLM engine with local Ollama and Gemini fallback.
    
    Features:
    - Local inference via Ollama for privacy and speed
    - Automatic fallback to Gemini if local latency > threshold
    - Conversation history management
    - Token counting and usage tracking
    - Structured output extraction
    """
    
    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "gemma3:1b",
        timeout_seconds: float = 3.5,
        enable_fallback: bool = True,
        gemini_api_key: Optional[str] = None
    ):
        """
        Initialize the LLM engine.
        
        Args:
            ollama_base_url: Base URL for Ollama API
            ollama_model: Model to use with Ollama  
            timeout_seconds: Latency threshold for fallback
            enable_fallback: Whether to enable Gemini fallback
            gemini_api_key: API key for Gemini
        """
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model
        self.timeout_seconds = timeout_seconds
        self.enable_fallback = enable_fallback
        
        self._ollama_client = None
        self._gemini_fallback: Optional[GeminiFallback] = None
        self._ollama_available = False
        self._initialized = False
        
        if enable_fallback:
            self._gemini_fallback = get_gemini_fallback(api_key=gemini_api_key)
    
    async def initialize(self) -> bool:
        """
        Initialize both local and fallback LLM connections.
        
        Returns:
            True if at least one provider is available
        """
        if self._initialized:
            return True
        
        # Check Ollama availability
        self._ollama_available = await self._check_ollama()
        
        if self._ollama_available:
            logger.info(f"Ollama connected: {self.ollama_model}")
        else:
            logger.warning("Ollama not available")
        
        # Initialize Gemini fallback if enabled
        if self.enable_fallback and self._gemini_fallback:
            if self._gemini_fallback.initialize():
                logger.info("Gemini fallback ready")
            else:
                logger.warning("Gemini fallback unavailable")
        
        self._initialized = self._ollama_available or (
            self.enable_fallback and 
            self._gemini_fallback and 
            self._gemini_fallback.is_available()
        )
        
        return self._initialized
    
    async def _check_ollama(self) -> bool:
        """
        Check if Ollama is running and the model is available.
        
        Returns:
            True if Ollama is available
        """
        try:
            import ollama
            
            self._ollama_client = ollama.AsyncClient(host=self.ollama_base_url)
            
            # Check if model exists
            models = await self._ollama_client.list()
            available_models = [m.get("name", "") for m in models.get("models", [])]
            
            # Check for exact match or partial match
            model_found = any(
                self.ollama_model in m or m.startswith(self.ollama_model.split(":")[0])
                for m in available_models
            )
            
            if not model_found:
                logger.warning(
                    f"Model {self.ollama_model} not found. "
                    f"Available: {available_models}"
                )
                # Try to pull the model
                logger.info(f"Attempting to pull {self.ollama_model}...")
                try:
                    await self._ollama_client.pull(self.ollama_model)
                    logger.info(f"Successfully pulled {self.ollama_model}")
                    return True
                except Exception as pull_error:
                    logger.error(f"Failed to pull model: {pull_error}")
                    return False
            
            return True
            
        except ImportError:
            logger.error("ollama package not installed")
            return False
        except Exception as e:
            logger.error(f"Ollama connection error: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> LLMResponse:
        """
        Generate a response using the best available LLM.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            conversation_history: Previous conversation turns
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            LLMResponse with the generated text
        """
        if not self._initialized:
            await self.initialize()
        
        # Try Ollama first if available
        if self._ollama_available:
            response = await self._generate_ollama(
                prompt, system_prompt, conversation_history,
                temperature, max_tokens
            )
            
            # Check if we need fallback
            if response.success and response.latency_ms <= self.timeout_seconds * 1000:
                return response
            
            if not response.success:
                logger.warning(f"Ollama failed: {response.error}")
            else:
                logger.warning(
                    f"Ollama latency {response.latency_ms:.0f}ms > "
                    f"threshold {self.timeout_seconds * 1000:.0f}ms"
                )
        
        # Fallback to Gemini
        if self.enable_fallback and self._gemini_fallback:
            logger.info("Falling back to Gemini")
            return await self._generate_gemini(
                prompt, system_prompt, conversation_history
            )
        
        return LLMResponse(
            text="",
            provider=LLMProvider.NONE,
            latency_ms=0,
            tokens_used=0,
            success=False,
            error="No LLM provider available"
        )
    
    async def _generate_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str],
        conversation_history: Optional[List[Dict[str, str]]],
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """
        Generate using Ollama.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            conversation_history: Previous turns
            temperature: Sampling temperature
            max_tokens: Max tokens
            
        Returns:
            LLMResponse from Ollama
        """
        start_time = time.time()
        
        try:
            # Build messages
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            if conversation_history:
                messages.extend(conversation_history)
            
            messages.append({"role": "user", "content": prompt})
            
            # Generate
            response = await asyncio.wait_for(
                self._ollama_client.chat(
                    model=self.ollama_model,
                    messages=messages,
                    options={
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                ),
                timeout=self.timeout_seconds * 2  # Double timeout for the API call itself
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            text = response.get("message", {}).get("content", "")
            
            return LLMResponse(
                text=text,
                provider=LLMProvider.OLLAMA,
                latency_ms=latency_ms,
                tokens_used=response.get("eval_count", 0),
                success=True,
                metadata={
                    "model": self.ollama_model,
                    "total_duration": response.get("total_duration", 0),
                    "load_duration": response.get("load_duration", 0),
                    "eval_duration": response.get("eval_duration", 0)
                }
            )
            
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            return LLMResponse(
                text="",
                provider=LLMProvider.OLLAMA,
                latency_ms=latency_ms,
                tokens_used=0,
                success=False,
                error=f"Timeout after {latency_ms:.0f}ms"
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return LLMResponse(
                text="",
                provider=LLMProvider.OLLAMA,
                latency_ms=latency_ms,
                tokens_used=0,
                success=False,
                error=str(e)
            )
    
    async def _generate_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> LLMResponse:
        """
        Generate using Gemini fallback.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            conversation_history: Previous turns
            
        Returns:
            LLMResponse from Gemini
        """
        if not self._gemini_fallback:
            return LLMResponse(
                text="",
                provider=LLMProvider.GEMINI,
                latency_ms=0,
                tokens_used=0,
                success=False,
                error="Gemini fallback not configured"
            )
        
        gemini_response = await self._gemini_fallback.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history
        )
        
        return LLMResponse(
            text=gemini_response.text,
            provider=LLMProvider.GEMINI,
            latency_ms=gemini_response.latency_ms,
            tokens_used=gemini_response.tokens_used,
            success=gemini_response.success,
            error=gemini_response.error
        )
    
    def generate_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> LLMResponse:
        """
        Synchronous generation for non-async contexts.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            conversation_history: Previous turns
            temperature: Sampling temperature
            max_tokens: Max tokens
            
        Returns:
            LLMResponse
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.generate(
                prompt, system_prompt, conversation_history,
                temperature, max_tokens
            )
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the LLM engine."""
        return {
            "initialized": self._initialized,
            "ollama": {
                "available": self._ollama_available,
                "base_url": self.ollama_base_url,
                "model": self.ollama_model
            },
            "gemini": {
                "enabled": self.enable_fallback,
                "available": (
                    self._gemini_fallback.is_available() 
                    if self._gemini_fallback else False
                )
            },
            "timeout_seconds": self.timeout_seconds
        }


# Singleton instance
_llm_engine: Optional[LLMEngine] = None


def get_llm_engine(
    ollama_base_url: Optional[str] = None,
    ollama_model: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    enable_fallback: bool = True
) -> LLMEngine:
    """
    Get or create a singleton LLMEngine instance.
    
    Args:
        ollama_base_url: Ollama base URL
        ollama_model: Ollama model name
        timeout_seconds: Fallback timeout
        enable_fallback: Enable Gemini fallback
        
    Returns:
        LLMEngine instance
    """
    global _llm_engine
    
    if _llm_engine is None:
        _llm_engine = LLMEngine(
            ollama_base_url=ollama_base_url or os.getenv(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            ),
            ollama_model=ollama_model or os.getenv(
                "OLLAMA_MODEL", "gemma3:1b"
            ),
            timeout_seconds=timeout_seconds or float(
                os.getenv("LLM_TIMEOUT_SECONDS", "3.5")
            ),
            enable_fallback=enable_fallback
        )
    
    return _llm_engine
