"""Fire-and-forget usage event logging to Nexus."""

import asyncio
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def _send(payload: dict) -> None:
    s = get_settings()
    if not s.nexus_url or not s.nexus_api_key:
        return
    url = f"{s.nexus_url.rstrip('/')}/api/app-auth/usage"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                url,
                json=payload,
                headers={"X-API-Key": s.nexus_api_key, "Content-Type": "application/json"},
            )
    except Exception as exc:
        logger.debug("Usage log failed (non-critical): %s", exc)


def log_event(
    actor: str,
    event_type: str,
    event_data: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Schedule a fire-and-forget usage event. Safe to call from any async context."""
    payload = {
        "actor": actor,
        "event_type": event_type,
        "event_data": event_data or {},
        "ip_address": ip_address,
    }
    try:
        asyncio.create_task(_send(payload))
    except RuntimeError:
        pass


def get_client_ip(request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None
