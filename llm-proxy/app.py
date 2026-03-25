"""LLM Proxy: authenticates via X-Friend header, proxies to LM Studio, logs to Nexus."""

import logging
import os
import httpx
import asyncio

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import StreamingResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_FRIENDS = {f.strip() for f in os.environ.get("ALLOWED_FRIENDS", "Jim").split(",") if f.strip()}
LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://192.168.1.20:1234").rstrip("/")
NEXUS_URL = os.environ.get("NEXUS_URL", "").rstrip("/")
NEXUS_API_KEY = os.environ.get("NEXUS_API_KEY", "")
PORT = int(os.environ.get("PORT", "3094"))

app = FastAPI(title="LLM Proxy", docs_url=None, redoc_url=None)


async def _log_to_nexus(friend: str, path: str, body: dict, ip: str | None) -> None:
    if not NEXUS_URL or not NEXUS_API_KEY:
        return
    model = body.get("model", "unknown") if isinstance(body, dict) else "unknown"
    messages = body.get("messages", []) if isinstance(body, dict) else []
    payload = {
        "actor": friend,
        "event_type": "llm_request",
        "event_data": {
            "endpoint": path,
            "model": model,
            "messages": messages,
        },
        "ip_address": ip,
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{NEXUS_URL}/api/app-auth/usage",
                json=payload,
                headers={"X-API-Key": NEXUS_API_KEY, "Content-Type": "application/json"},
            )
    except Exception as exc:
        logger.debug("Nexus log failed (non-critical): %s", exc)


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
async def proxy(path: str, request: Request):
    friend = request.headers.get("x-friend", "").strip()

    if friend not in ALLOWED_FRIENDS:
        return Response(
            content='{"error": "Who are you? Set the X-Friend header."}',
            status_code=401,
            media_type="application/json",
        )

    body_bytes = await request.body()
    body_json: dict = {}
    if body_bytes:
        try:
            import json
            body_json = json.loads(body_bytes)
        except Exception:
            pass

    ip = _get_client_ip(request)

    # Fire-and-forget logging for POST requests (chat completions etc.)
    if request.method == "POST":
        asyncio.create_task(_log_to_nexus(friend, f"/{path}", body_json, ip))

    # Forward headers, strip hop-by-hop and our custom header
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("x-friend", "host", "connection", "transfer-encoding")
    }

    target_url = f"{LM_STUDIO_URL}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    is_stream = body_json.get("stream", False)

    async with httpx.AsyncClient(timeout=None) as client:
        if is_stream:
            async def stream_gen():
                async with client.stream(
                    request.method,
                    target_url,
                    headers=forward_headers,
                    content=body_bytes,
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk

            return StreamingResponse(stream_gen(), media_type="text/event-stream")
        else:
            resp = await client.request(
                request.method,
                target_url,
                headers=forward_headers,
                content=body_bytes,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
            )
