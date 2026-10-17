"""
voice/router.py – FastAPI routes for speech-to-text, text-to-speech, and voice sessions.
"""

from __future__ import annotations

import io
import logging
from typing import Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.database.models import User
from backend.voice.stt import STTFactory
from backend.voice.tts import TTSFactory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/voice", tags=["voice"])

ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mp3",
    "audio/mpeg",
    "audio/ogg",
    "audio/webm",
    "audio/flac",
    "audio/m4a",
    "audio/mp4",
}
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB


class SynthesizeRequest(BaseModel):
    text: str
    voice: str | None = None
    speed: float = 1.0
    provider: str | None = None


class VoiceInfoResponse(BaseModel):
    id: str
    name: str
    language: str
    gender: str | None
    provider: str


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("en"),
    current_user: User = Depends(get_current_user),
):
    """Transcribe an uploaded voice audio file to text."""
    content_type = file.content_type or ""
    if content_type not in ALLOWED_AUDIO_TYPES and not file.filename.endswith((".wav", ".mp3", ".webm", ".ogg")):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio type: {content_type}. Supported: wav, mp3, ogg, webm.",
        )

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file exceeds maximum size of 25MB.",
        )

    try:
        stt = STTFactory.create()
        result = await stt.transcribe(audio_bytes, language=language, filename=file.filename or "audio.wav")
        return {
            "text": result.text,
            "language": result.language,
            "confidence": result.confidence,
            "provider": result.provider,
            "duration_seconds": result.duration_seconds,
        }
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(exc)}",
        )


@router.post("/synthesize")
async def synthesize_speech(
    req: SynthesizeRequest,
    current_user: User = Depends(get_current_user),
):
    """Convert text to speech audio stream."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    try:
        tts = TTSFactory.create(req.provider)
        audio_data = await tts.synthesize(req.text, voice=req.voice, speed=req.speed)
        if not audio_data:
            # Browser TTS provider: instructions returned for client-side synthesis
            return {"status": "client_synthesis", "text": req.text}

        return Response(content=audio_data, media_type="audio/mpeg")
    except Exception as exc:
        logger.exception("Speech synthesis failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech synthesis failed: {str(exc)}",
        )


@router.get("/voices", response_model=list[VoiceInfoResponse])
async def list_voices(
    provider: str | None = None,
    current_user: User = Depends(get_current_user),
):
    """List available text-to-speech voices."""
    tts = TTSFactory.create(provider)
    voices = tts.get_available_voices()
    return [
        VoiceInfoResponse(
            id=v.id,
            name=v.name,
            language=v.language,
            gender=v.gender,
            provider=v.provider,
        )
        for v in voices
    ]
