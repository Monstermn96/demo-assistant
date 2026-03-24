import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=settings.memory_url,
            timeout=httpx.Timeout(20.0, connect=5.0),
            headers=_auth_headers(),
        )
    return _http_client


def _auth_headers() -> dict[str, str]:
    if settings.memory_api_key:
        return {"Authorization": f"Bearer {settings.memory_api_key}"}
    return {}


class MemoryClient:
    """Centralized client for all arim-memory service interactions.

    Provides connection pooling, graceful degradation, and consistent
    user_id scoping so each user's memories are isolated.
    """

    @staticmethod
    async def is_healthy() -> bool:
        try:
            resp = await _get_client().get("/health", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    async def store(
        content: str,
        user_id: int,
        *,
        tier: str = "auto",
        topic: str | None = None,
        importance: float = 0.5,
        source: str = "chat",
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "content": content,
            "tier": tier,
            "importance": importance,
            "user_id": user_id,
            "source": source,
        }
        if topic:
            payload["topic"] = topic
        if metadata:
            payload["metadata"] = metadata

        return await _request("POST", "/memory/store", json=payload)

    @staticmethod
    async def search(
        query: str,
        user_id: int,
        *,
        limit: int = 10,
        tiers: list[str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "user_id": user_id,
        }
        if tiers:
            payload["tiers"] = tiers
        return await _request("POST", "/memory/search", json=payload)

    @staticmethod
    async def recall(
        user_id: int,
        *,
        limit: int = 20,
        topic: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "limit": limit,
            "user_id": user_id,
        }
        if topic:
            payload["topic"] = topic
        return await _request("POST", "/memory/recall", json=payload)

    @staticmethod
    async def get_profile(user_id: int) -> dict[str, Any]:
        return await _request("GET", "/memory/profile", params={"user_id": user_id})

    @staticmethod
    async def update_profile(
        user_id: int,
        key: str,
        value: str,
        *,
        confidence: float = 1.0,
        source: str = "explicit",
    ) -> dict[str, Any]:
        return await _request("PUT", "/memory/profile", json={
            "user_id": user_id,
            "key": key,
            "value": value,
            "confidence": confidence,
            "source": source,
        })

    @staticmethod
    async def get_procedural_rules(
        user_id: int,
        category: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"user_id": user_id}
        if category:
            params["category"] = category
        return await _request("GET", "/memory/procedural", params=params)

    @staticmethod
    async def add_procedural_rule(
        user_id: int,
        name: str,
        rule: str,
        *,
        category: str = "general",
        priority: float = 0.5,
    ) -> dict[str, Any]:
        return await _request("POST", "/memory/procedural", json={
            "user_id": user_id,
            "name": name,
            "rule": rule,
            "category": category,
            "priority": priority,
        })

    @staticmethod
    async def delete(
        memory_id: str,
        user_id: int,
    ) -> dict[str, Any]:
        return await _request(
            "DELETE", f"/memory/{memory_id}", params={"user_id": user_id}
        )

    @staticmethod
    async def get_stats(user_id: int) -> dict[str, Any]:
        return await _request("GET", "/memory/stats", params={"user_id": user_id})

    @staticmethod
    async def load_user_context(user_id: int) -> str:
        """Load profile + recent procedural rules into a context string
        suitable for injecting into the system prompt."""
        parts: list[str] = []

        profile = await MemoryClient.get_profile(user_id)
        if not profile.get("_error"):
            entries = profile.get("profile", {})
            if entries:
                lines = [f"- {k}: {v['value']}" for k, v in entries.items()]
                parts.append("User profile:\n" + "\n".join(lines))

        # No category filter: main prompt gets all procedural rules (top 10).
        rules = await MemoryClient.get_procedural_rules(user_id)
        if not rules.get("_error"):
            rule_list = rules.get("rules", [])
            if rule_list:
                lines = [f"- {r['name']}: {r['rule']}" for r in rule_list[:10]]
                parts.append("Learned interaction rules:\n" + "\n".join(lines))

        return "\n\n".join(parts)


async def _request(
    method: str, path: str, **kwargs: Any
) -> dict[str, Any]:
    """Execute an HTTP request against arim-memory with graceful error handling."""
    if not settings.memory_enabled:
        return {"_error": "memory_disabled", "_message": "Memory service is disabled"}

    try:
        client = _get_client()
        resp = await client.request(method, path, **kwargs)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return {"results": data}
        return data
    except httpx.ConnectError:
        logger.warning("Memory service unreachable at %s", settings.memory_url)
        return {"_error": "unreachable", "_message": "Memory service is not running"}
    except httpx.TimeoutException:
        logger.warning("Memory service timed out")
        return {"_error": "timeout", "_message": "Memory service timed out"}
    except httpx.HTTPStatusError as exc:
        logger.warning("Memory service returned %s: %s", exc.response.status_code, exc.response.text[:200])
        return {"_error": "http_error", "_message": f"Memory service error ({exc.response.status_code})"}
    except Exception as exc:
        logger.exception("Unexpected memory client error")
        return {"_error": "unknown", "_message": str(exc)}
