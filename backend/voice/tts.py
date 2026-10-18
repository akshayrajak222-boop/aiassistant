"""
voice/tts.py – Text-to-Speech abstraction layer.
"""

from __future__ import annotations

import io
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VoiceInfo:
    id: str
    name: str
    language: str
    gender: Optional[str] = None
    provider: str = "browser"


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> bytes:
        """Synthesize text to raw audio bytes (MP3/WAV/OGG)."""
        pass

    @abstractmethod
    def get_available_voices(self) -> list[VoiceInfo]:
        """List available voices for this provider."""
        pass


class BrowserTTSProvider(TTSProvider):
    """Browser-based speech synthesis using Web Speech SpeechSynthesis API.

    Returns empty bytes because the browser natively generates and plays audio.
    """

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> bytes:
        # Browser client renders speech directly; no server computation needed
        return b""

    def get_available_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(id="browser-default", name="Browser Default Voice", language="en-US", provider="browser"),
            VoiceInfo(id="browser-natural", name="Natural Voice", language="en-US", provider="browser"),
        ]


class OpenAITTSProvider(TTSProvider):
    """OpenAI Text-to-Speech API provider (tts-1, tts-1-hd)."""

    def __init__(self, model: str = "tts-1") -> None:
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        import openai
        self._client = openai.AsyncOpenAI(api_key=self.api_key)

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = "alloy",
        speed: float = 1.0,
    ) -> bytes:
        selected_voice = voice or "alloy"
        response = await self._client.audio.speech.create(
            model=self.model,
            voice=selected_voice,  # type: ignore
            input=text,
            speed=max(0.25, min(4.0, speed)),
        )
        return response.content

    def get_available_voices(self) -> list[VoiceInfo]:
        voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        return [
            VoiceInfo(id=v, name=v.capitalize(), language="en", provider="openai")
            for v in voices
        ]


class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs TTS provider for ultra-realistic voices."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not set.")

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> bytes:
        import httpx
        voice_id = (
            voice
            or os.environ.get("ELEVENLABS_VOICE_ID")
            or os.environ.get("TTS_VOICE")
            or "21m00Tcm4TlvDq8ikWAM"
        )
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.content

    def get_available_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(id="21m00Tcm4TlvDq8ikWAM", name="Rachel (Default)", language="en", provider="elevenlabs"),
            VoiceInfo(id="AZnzlk1XvdvUeBnXmlld", name="Domi", language="en", provider="elevenlabs"),
            VoiceInfo(id="EXAVITQu4vr4xnSDxMaL", name="Bella", language="en", provider="elevenlabs"),
            VoiceInfo(id="ErXwobaYiN019PkySvjV", name="Antoni", language="en", provider="elevenlabs"),
            VoiceInfo(id="MF3mGyEYCl7XYWbV9V6O", name="Elli", language="en", provider="elevenlabs"),
            VoiceInfo(id="TxGEqnHWrfWFTfGW9XjX", name="Josh", language="en", provider="elevenlabs"),
            VoiceInfo(id="VR6AewLTigWG4xSOukaG", name="Arnold", language="en", provider="elevenlabs"),
            VoiceInfo(id="pNInz6obpgDQGcFmaJgB", name="Adam", language="en", provider="elevenlabs"),
            VoiceInfo(id="yoZ06aMxZJJ28mfd3POQ", name="Sam", language="en", provider="elevenlabs"),
        ]


class TTSFactory:
    @staticmethod
    def create(provider_name: Optional[str] = None) -> TTSProvider:
        p = (provider_name or os.environ.get("TTS_PROVIDER", "browser")).lower()
        if p == "openai":
            try:
                return OpenAITTSProvider()
            except Exception as e:
                logger.warning(f"OpenAI TTS init failed: {e}. Falling back to Browser TTS.")
                return BrowserTTSProvider()
        elif p == "elevenlabs":
            try:
                return ElevenLabsTTSProvider()
            except Exception as e:
                logger.warning(f"ElevenLabs TTS init failed: {e}. Falling back to Browser TTS.")
                return BrowserTTSProvider()
        return BrowserTTSProvider()
