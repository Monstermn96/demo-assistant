"""LLM Proxy: authenticates via X-Friend header, proxies to LM Studio, logs to Nexus."""

import json
import logging
import os
import asyncio

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_FRIENDS = {f.strip() for f in os.environ.get("ALLOWED_FRIENDS", "Jim").split(",") if f.strip()}
LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://192.168.1.20:1234").rstrip("/")
NEXUS_URL = os.environ.get("NEXUS_URL", "").rstrip("/")
NEXUS_API_KEY = os.environ.get("NEXUS_API_KEY", "")
PORT = int(os.environ.get("PORT", "3094"))

app = FastAPI(title="LLM Proxy", docs_url=None, redoc_url=None)


async def _log_to_nexus(payload: dict) -> None:
    if not NEXUS_URL or not NEXUS_API_KEY:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{NEXUS_URL}/api/app-auth/usage",
                json=payload,
                headers={"X-API-Key": NEXUS_API_KEY, "Content-Type": "application/json"},
            )
            if resp.status_code != 201:
                logger.warning("Nexus usage log returned %d: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("Nexus usage log failed: %s", exc)


def _build_event(
    friend: str, path: str, body: dict, ip: str | None,
    status_code: int | None = None, response_body: str | None = None,
    error: str | None = None,
) -> dict:
    model = body.get("model", "unknown") if isinstance(body, dict) else "unknown"
    messages = body.get("messages", []) if isinstance(body, dict) else []

    event_data: dict = {
        "endpoint": path,
        "model": model,
        "messages": messages,
    }
    if status_code is not None:
        event_data["status_code"] = status_code
    if error:
        event_data["error"] = error
    if response_body and status_code and status_code >= 400:
        try:
            err_json = json.loads(response_body)
            event_data["error_detail"] = err_json.get("error", {}).get("message", response_body[:500]) if isinstance(err_json.get("error"), dict) else str(err_json.get("error", response_body[:500]))
        except Exception:
            event_data["error_detail"] = response_body[:500]

    return {
        "actor": friend,
        "event_type": "llm_request",
        "event_data": event_data,
        "ip_address": ip,
    }


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
            body_json = json.loads(body_bytes)
        except Exception:
            pass

    ip = _get_client_ip(request)

    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("x-friend", "host", "connection", "transfer-encoding")
    }

    target_url = f"{LM_STUDIO_URL}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    is_stream = body_json.get("stream", False)

    if request.method == "POST" and is_stream:
        async def stream_gen():
            status = None
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream(
                        request.method, target_url,
                        headers=forward_headers, content=body_bytes,
                    ) as resp:
                        status = resp.status_code
                        async for chunk in resp.aiter_bytes():
                            yield chunk
            except Exception as exc:
                event = _build_event(friend, f"/{path}", body_json, ip, error=str(exc))
                asyncio.create_task(_log_to_nexus(event))
                raise
            finally:
                if status is not None:
                    event = _build_event(friend, f"/{path}", body_json, ip, status_code=status)
                    asyncio.create_task(_log_to_nexus(event))

        return StreamingResponse(stream_gen(), media_type="text/event-stream")

    async with httpx.AsyncClient(timeout=None) as client:
        try:
            resp = await client.request(
                request.method, target_url,
                headers=forward_headers, content=body_bytes,
            )
        except Exception as exc:
            if request.method == "POST":
                event = _build_event(friend, f"/{path}", body_json, ip, error=str(exc))
                asyncio.create_task(_log_to_nexus(event))
            return Response(
                content=json.dumps({"error": f"Upstream error: {exc}"}),
                status_code=502,
                media_type="application/json",
            )

        if request.method == "POST":
            event = _build_event(
                friend, f"/{path}", body_json, ip,
                status_code=resp.status_code,
                response_body=resp.text if resp.status_code >= 400 else None,
            )
            asyncio.create_task(_log_to_nexus(event))

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )
