"""
novaTech Voice Package

Integrates Open-Source Whisper STT and Open-Source Piper TTS.
"""

from backend.voice.stt_whisper import transcribe_audio_bytes
from backend.voice.tts_piper import synthesize_piper_speech

__all__ = ["transcribe_audio_bytes", "synthesize_piper_speech"]

