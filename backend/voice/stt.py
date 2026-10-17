"""
STT (Speech-to-Text) abstraction layer.

Providers
---------
WhisperSTTProvider  – calls OpenAI Whisper API.
BrowserSTTProvider  – stub; browser already transcribed, receives text directly.
"""
from __future__ import annotations

import io
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class TranscriptionResult:
    text: str
    language: str
    confidence: float  # 0.0 – 1.0; -1 if unknown
    provider: str
    duration_seconds: Optional[float] = None
    words: list[dict] = field(default_factory=list)  # word-level timestamps if available


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "en",
        *,
        prompt: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio bytes to text.

        Parameters
        ----------
        audio_data:
            Raw audio bytes (wav / mp3 / ogg / webm).
        language:
            BCP-47 language hint (e.g. 'en', 'fr').
        prompt:
            Optional previous context to improve accuracy.
        """


# ---------------------------------------------------------------------------
# OpenAI Whisper provider
# ---------------------------------------------------------------------------


class WhisperSTTProvider(STTProvider):
    """
    Uses the OpenAI Whisper API (whisper-1 model) for transcription.

    Required env vars
    -----------------
    OPENAI_API_KEY
    """

    def __init__(
        self,
        model: str = "whisper-1",
        response_format: str = "verbose_json",
    ) -> None:
        self._model = model
        self._response_format = response_format
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        # Import lazily to allow the module to load without openai installed
        import openai
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "en",
        *,
        prompt: Optional[str] = None,
        filename: str = "audio.wav",
    ) -> TranscriptionResult:
        kwargs: dict = {
            "model": self._model,
            "file": (filename, io.BytesIO(audio_data), "audio/wav"),
            "language": language,
            "response_format": self._response_format,
        }
        if prompt:
            kwargs["prompt"] = prompt

        try:
            response = await self._client.audio.transcriptions.create(**kwargs)
        except Exception as exc:
            logger.error("Whisper transcription failed: %s", exc)
            raise

        # verbose_json returns a rich object
        text: str = getattr(response, "text", "") or ""
        duration: Optional[float] = getattr(response, "duration", None)
        words_raw: list = getattr(response, "words", []) or []
        words: list[dict] = [
            {
                "word": w.get("word", ""),
                "start": w.get("start", 0),
                "end": w.get("end", 0),
            }
            for w in words_raw
        ]

        return TranscriptionResult(
            text=text.strip(),
            language=getattr(response, "language", language),
            confidence=-1.0,  # Whisper API doesn't return per-utterance confidence
            provider="whisper",
            duration_seconds=duration,
            words=words,
        )


# ---------------------------------------------------------------------------
# Browser STT stub provider
# ---------------------------------------------------------------------------


class BrowserSTTProvider(STTProvider):
    """
    Stub provider used when STT is performed in the browser.

    The browser sends already-transcribed text; this endpoint simply wraps it
    in a TranscriptionResult for uniform handling downstream.
    """

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "en",
        *,
        text: str = "",
        confidence: float = -1.0,
        prompt: Optional[str] = None,
    ) -> TranscriptionResult:
        # audio_data is ignored; text was produced by Web Speech API
        return TranscriptionResult(
            text=text.strip(),
            language=language,
            confidence=confidence,
            provider="browser",
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class STTFactory:
    @staticmethod
    def create(provider: Optional[str] = None) -> STTProvider:
        """
        Instantiate the STT provider specified by *provider* or the
        ``STT_PROVIDER`` environment variable.

        Supported values: ``whisper`` (default), ``browser``.
        """
        name = (provider or os.environ.get("STT_PROVIDER", "whisper")).lower()
        if name == "whisper":
            return WhisperSTTProvider()
        if name == "browser":
            return BrowserSTTProvider()
        raise ValueError(f"Unknown STT provider: '{name}'. Expected 'whisper' or 'browser'.")
