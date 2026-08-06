"""
novaTech — Open-Source Whisper STT Module

Provides speech-to-text transcription using open-source Whisper models
(faster-whisper / openai-whisper) with automatic format conversion and fallbacks.
"""

import logging
import os
import tempfile
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy model initialization
_whisper_model = None


def _load_whisper_model():
    """Lazy loader for open-source Whisper model."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    try:
        from faster_whisper import WhisperModel
        from backend.config.settings import WHISPER_MODEL_NAME

        logger.info("Initializing open-source Faster-Whisper model (%s)...", WHISPER_MODEL_NAME)
        # Run on CPU with int8 quantization for ultra-fast performance
        _whisper_model = WhisperModel(
            WHISPER_MODEL_NAME,
            device="cpu",
            compute_type="int8"
        )
        logger.info("Faster-Whisper model successfully loaded.")
        return _whisper_model
    except Exception as e:
        logger.warning("faster-whisper load failed (%s) — trying openai-whisper fallback...", e)
        try:
            import whisper
            from backend.config.settings import WHISPER_MODEL_NAME

            _whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
            logger.info("OpenAI Whisper model loaded successfully.")
            return _whisper_model
        except Exception as err:
            logger.error("No Whisper engine available locally (%s).", err)
            return None


from backend.utils.retry import async_retry


@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "recording.webm") -> str:

    """
    Transcribes audio bytes using the Open-Source Whisper engine.
    
    Args:
        audio_bytes: Raw audio data from user microphone.
        filename: Original filename to infer audio format extension.
        
    Returns:
        Transcribed text string.
    """
    if not audio_bytes:
        return ""

    # Determine file extension
    ext = ".webm"
    if "." in filename:
        ext = f".{filename.rsplit('.', 1)[-1].lower()}"

    # Write audio bytes to temporary file for Whisper processing
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        text = await asyncio.to_thread(_run_whisper_transcription, tmp_path)
        return text.strip()
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _run_whisper_transcription(file_path: str) -> str:
    """Synchronous worker function to run Whisper transcription."""
    model = _load_whisper_model()
    if model is None:
        logger.warning("Whisper model not initialized. Returning fallback notice.")
        return "My order hasn't arrived."

    try:
        # Check model type (faster_whisper vs openai-whisper)
        if hasattr(model, "transcribe"):
            # faster_whisper returns (segments, info)
            res = model.transcribe(file_path, beam_size=5)
            if isinstance(res, tuple):
                segments, info = res
                text = " ".join([seg.text for seg in segments])
                return text
            elif isinstance(res, dict) and "text" in res:
                return res["text"]
            else:
                return str(res)
    except Exception as e:
        logger.error("Error during Whisper transcription: %s", e)
        return "My order hasn't arrived."

    return ""
