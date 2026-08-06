"""
novaTech — Open-Source Piper TTS Module

Provides neural text-to-speech synthesis using open-source Piper TTS engine
with fast WAV audio stream generation.
"""

import logging
import os
import subprocess
import tempfile
import asyncio
import wave
import io
from typing import Optional

logger = logging.getLogger(__name__)

# Cache loaded piper voice instance if using Python bindings
_piper_voice = None


def _clean_text_for_piper(text: str) -> str:
    """Removes markdown tags, code blocks, and symbols for clean spoken audio."""
    import re
    if not text:
        return ""
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'#+\s+', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'[-•*]\s+', '', text)
    text = re.sub(r'[\n\r]+', ' ', text)
    return text.strip()


from backend.utils.retry import async_retry


@async_retry(max_attempts=3, min_wait=0.5, max_wait=4.0)
async def synthesize_piper_speech(text: str, voice: str = "en_US-lessac-medium") -> bytes:

    """
    Synthesizes speech using the Open-Source Piper TTS engine.
    
    Args:
        text: Text to synthesize.
        voice: Piper voice model name.
        
    Returns:
        Audio bytes (WAV format).
    """
    clean_text = _clean_text_for_piper(text)
    if not clean_text:
        return b""

    # Truncate text to max 2000 chars for fast response
    clean_text = clean_text[:2000]

    return await asyncio.to_thread(_run_piper_synthesis, clean_text, voice)


def _run_piper_synthesis(text: str, voice_model: str) -> bytes:
    """Synchronous worker function to run Piper synthesis."""
    # Attempt 1: Piper CLI execution if available in PATH
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_out:
            tmp_wav_path = tmp_out.name

        cmd = ["piper", "--model", voice_model, "--output_file", tmp_wav_path]
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        process.communicate(input=text)

        if process.returncode == 0 and os.path.exists(tmp_wav_path) and os.path.getsize(tmp_wav_path) > 0:
            with open(tmp_wav_path, "rb") as f:
                audio_bytes = f.read()
            os.remove(tmp_wav_path)
            logger.info("Piper CLI synthesized %d audio bytes.", len(audio_bytes))
            return audio_bytes
        if os.path.exists(tmp_wav_path):
            os.remove(tmp_wav_path)
    except Exception as e:
        logger.debug("Piper CLI not available (%s), trying python fallback...", e)

    # Attempt 2: Python piper-tts package bindings
    try:
        from piper import PiperVoice
        from backend.config.settings import PIPER_VOICE_MODEL

        voice_path = os.path.join("backend/voice/models", f"{PIPER_VOICE_MODEL}.onnx")
        if os.path.exists(voice_path):
            voice = PiperVoice.load(voice_path)
            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wav_file:
                voice.synthesize(text, wav_file)
            return wav_io.getvalue()
    except Exception as e:
        logger.debug("Piper Python bindings not initialized (%s).", e)

    # Attempt 3: Open-Source gTTS fallback generator for clean audio output
    try:
        from gtts import gTTS
        fp = io.BytesIO()
        tts = gTTS(text=text, lang='en', slow=False)
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception as err:
        logger.warning("gTTS fallback error (%s). Generating silence WAV placeholder.", err)

    # Attempt 4: Generate minimal valid WAV file header as safe fallback
    return _generate_beep_wav()


def _generate_beep_wav() -> bytes:
    """Generates a simple, valid PCM WAV audio byte sequence."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav_file:
        wav_file.setnchannels(1)     # Mono
        wav_file.setsampwidth(2)    # 16-bit
        wav_file.setframerate(22050) # 22.05 kHz sample rate
        # 0.5s of zero PCM samples
        frames = b'\x00\x00' * 11025
        wav_file.writeframes(frames)
    return buf.getvalue()
