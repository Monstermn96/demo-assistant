import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from app.auth.middleware import get_current_user
from app.db.models import User
from app.config import get_settings
from app.tts import client as tts_client

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/tts", tags=["tts"])


class TTSRequest(BaseModel):
    text: str = Field(..., max_length=5000)
    voice: str = "default"


@router.post("")
async def text_to_speech(
    body: TTSRequest,
    user: User = Depends(get_current_user),
):
    if not settings.tts_enabled:
        raise HTTPException(status_code=503, detail="TTS is not enabled")

    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text is empty")

    try:
        audio_bytes = await tts_client.generate_speech(body.text, body.voice)
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=speech.wav"},
        )
    except Exception as e:
        logger.exception("TTS request failed")
        raise HTTPException(status_code=503, detail=f"TTS service unavailable: {e}")


@router.get("/voices")
async def get_voices(user: User = Depends(get_current_user)):
    if not settings.tts_enabled:
        raise HTTPException(status_code=503, detail="TTS is not enabled")

    try:
        voices = await tts_client.list_voices()
        return {"voices": voices}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TTS service unavailable: {e}")


@router.get("/status")
async def tts_status(user: User = Depends(get_current_user)):
    if not settings.tts_enabled:
        return {"enabled": False, "available": False}

    available = await tts_client.check_health()
    return {"enabled": True, "available": available}
