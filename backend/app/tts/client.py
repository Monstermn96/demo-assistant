import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=60.0)
    return _client


async def generate_speech(text: str, voice: str = "default") -> bytes:
    client = _get_client()
    url = f"{settings.tts_url}/v1/audio/speech"
    payload = {"input": text, "voice": voice}
    resp = await client.post(url, json=payload)
    resp.raise_for_status()
    return resp.content


async def list_voices() -> list[dict]:
    client = _get_client()
    url = f"{settings.tts_url}/v1/audio/voices"
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json().get("voices", [])


async def check_health() -> bool:
    try:
        client = _get_client()
        resp = await client.get(f"{settings.tts_url}/health", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False
