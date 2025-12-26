# =============================================================================
# RealtyAssistant AI Agent - Whisper Speech-to-Text Engine
# =============================================================================
"""
Local speech-to-text implementation using faster-whisper for CPU inference.
Optimized for real-time transcription with minimal latency.
"""

import os
import io
import logging
from typing import Optional, Tuple
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class WhisperEngine:
    """
    Speech-to-Text engine using faster-whisper for local CPU inference.
    
    Features:
    - CPU-optimized inference using CTranslate2
    - Support for multiple model sizes
    - Real-time transcription capability
    - Audio preprocessing for optimal results
    """
    
    SUPPORTED_MODELS = [
        "tiny.en", "base.en", "small.en", "medium.en",
        "tiny", "base", "small", "medium", "large-v2", "large-v3",
        "distil-large-v3"
    ]
    
    def __init__(
        self,
        model_name: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8"
    ):
        """
        Initialize the Whisper engine.
        
        Args:
            model_name: Name of the whisper model to use
            device: Device for inference (cpu for this project)
            compute_type: Quantization type for CPU (int8 recommended)
        """
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self._initialized = False
        
    def initialize(self) -> bool:
        """
        Lazy initialization of the Whisper model.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True
            
        try:
            from faster_whisper import WhisperModel
            
            logger.info(f"Loading Whisper model: {self.model_name}")
            logger.info(f"Device: {self.device}, Compute type: {self.compute_type}")
            
            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=os.cpu_count() or 4,
                num_workers=2
            )
            
            self._initialized = True
            logger.info("Whisper model loaded successfully")
            return True
            
        except ImportError as e:
            logger.error(f"faster-whisper not installed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Whisper model: {e}")
            return False
    
    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: str = "en"
    ) -> Tuple[str, float]:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Numpy array of audio samples
            sample_rate: Audio sample rate (16kHz recommended)
            language: Language code for transcription
            
        Returns:
            Tuple of (transcription text, confidence score)
        """
        if not self._initialized:
            if not self.initialize():
                return "", 0.0
        
        try:
            # Ensure audio is in the correct format
            audio_data = self._preprocess_audio(audio_data, sample_rate)
            
            # Transcribe
            segments, info = self.model.transcribe(
                audio_data,
                language=language,
                beam_size=5,
                best_of=5,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=400
                )
            )
            
            # Collect all segments
            full_text = ""
            total_confidence = 0.0
            segment_count = 0
            
            for segment in segments:
                full_text += segment.text
                total_confidence += segment.avg_logprob
                segment_count += 1
            
            # Calculate average confidence
            avg_confidence = (total_confidence / segment_count) if segment_count > 0 else 0.0
            # Convert log probability to a 0-1 confidence score
            confidence_score = min(1.0, max(0.0, 1.0 + avg_confidence))
            
            logger.debug(f"Transcription: {full_text.strip()}")
            logger.debug(f"Confidence: {confidence_score:.2f}")
            
            return full_text.strip(), confidence_score
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return "", 0.0
    
    def transcribe_file(
        self,
        file_path: str,
        language: str = "en"
    ) -> Tuple[str, float]:
        """
        Transcribe audio from a file.
        
        Args:
            file_path: Path to the audio file
            language: Language code for transcription
            
        Returns:
            Tuple of (transcription text, confidence score)
        """
        if not self._initialized:
            if not self.initialize():
                return "", 0.0
        
        try:
            if not Path(file_path).exists():
                logger.error(f"Audio file not found: {file_path}")
                return "", 0.0
            
            segments, info = self.model.transcribe(
                file_path,
                language=language,
                beam_size=5,
                best_of=5,
                temperature=0.0,
                vad_filter=True
            )
            
            full_text = ""
            total_confidence = 0.0
            segment_count = 0
            
            for segment in segments:
                full_text += segment.text
                total_confidence += segment.avg_logprob
                segment_count += 1
            
            avg_confidence = (total_confidence / segment_count) if segment_count > 0 else 0.0
            confidence_score = min(1.0, max(0.0, 1.0 + avg_confidence))
            
            return full_text.strip(), confidence_score
            
        except Exception as e:
            logger.error(f"File transcription error: {e}")
            return "", 0.0
    
    def _preprocess_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> np.ndarray:
        """
        Preprocess audio data for optimal transcription.
        
        Args:
            audio_data: Raw audio numpy array
            sample_rate: Current sample rate
            
        Returns:
            Preprocessed audio array
        """
        # Convert to float32 if needed
        if audio_data.dtype != np.float32:
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32768.0
            elif audio_data.dtype == np.int32:
                audio_data = audio_data.astype(np.float32) / 2147483648.0
            else:
                audio_data = audio_data.astype(np.float32)
        
        # Convert stereo to mono if needed
        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # Resample to 16kHz if needed
        if sample_rate != 16000:
            from scipy import signal
            num_samples = int(len(audio_data) * 16000 / sample_rate)
            audio_data = signal.resample(audio_data, num_samples)
        
        return audio_data
    
    def is_available(self) -> bool:
        """Check if the Whisper engine can be used."""
        try:
            from faster_whisper import WhisperModel
            return True
        except ImportError:
            return False
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "compute_type": self.compute_type,
            "initialized": self._initialized,
            "available": self.is_available()
        }


# Singleton instance for shared use
_whisper_instance: Optional[WhisperEngine] = None


def get_whisper_engine(
    model_name: str = "base.en",
    device: str = "cpu",
    compute_type: str = "int8"
) -> WhisperEngine:
    """
    Get or create a singleton WhisperEngine instance.
    
    Args:
        model_name: Model to use (only used on first call)
        device: Device for inference
        compute_type: Quantization type
        
    Returns:
        WhisperEngine instance
    """
    global _whisper_instance
    
    if _whisper_instance is None:
        _whisper_instance = WhisperEngine(
            model_name=model_name,
            device=device,
            compute_type=compute_type
        )
    
    return _whisper_instance
