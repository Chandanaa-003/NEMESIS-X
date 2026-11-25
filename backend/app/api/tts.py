from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User
from app.services.tts_service import (
    TtsUnavailableError,
    get_kannada_tts_status,
    synthesize_kannada_speech,
)

router = APIRouter(prefix="/tts", tags=["Text-to-Speech"])


class KannadaTtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@router.get(
    "/kannada/status",
    summary="Inspect backend Kannada TTS fallback availability and dynamically discovered voices",
)
async def kannada_tts_status(
    _current_user: User = Depends(get_current_user),
) -> dict:
    """Return dynamic edge-tts Kannada voice availability without exposing user data."""
    return await get_kannada_tts_status()


@router.post(
    "/kannada",
    summary="Synthesize Kannada announcement audio via backend edge-tts fallback",
)
async def synthesize_kannada_tts(
    payload: KannadaTtsRequest,
    _current_user: User = Depends(get_current_user),
) -> Response:
    """Generate MP3 audio for Kannada text using dynamically discovered kn-IN voice."""
    try:
        audio_bytes, voice_name, cached = await synthesize_kannada_speech(payload.text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except TtsUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "X-TTS-Provider": "edge-tts",
            "X-TTS-Voice": voice_name,
            "X-TTS-Cached": "true" if cached else "false",
        },
    )
