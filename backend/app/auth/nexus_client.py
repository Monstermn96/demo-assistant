import httpx
from app.config import get_settings


class NexusError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class NexusClient:
    def __init__(self):
        s = get_settings()
        self.base_url = s.nexus_url.rstrip("/")
        self.api_key = s.nexus_api_key

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }

    async def _request(self, method: str, path: str, **kwargs) -> dict | None:
        url = f"{self.base_url}/api/app-auth{path}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.request(method, url, headers=self._headers(), **kwargs)

        if resp.status_code == 204:
            return None

        data = resp.json()
        if not resp.is_success:
            raise NexusError(resp.status_code, data.get("detail", f"Nexus error {resp.status_code}"))
        return data

    async def register(self, username: str, password: str) -> dict:
        return await self._request("POST", "/register", json={"username": username, "password": password})

    async def login(self, username: str, password: str) -> dict:
        return await self._request("POST", "/login", json={"username": username, "password": password})

    async def validate_session(self, session_token: str) -> dict | None:
        try:
            return await self._request("POST", "/validate", json={"session_token": session_token})
        except NexusError:
            return None

    async def logout(self, session_token: str) -> None:
        try:
            await self._request("POST", "/logout", json={"session_token": session_token})
        except NexusError:
            pass

    async def list_api_keys(self, user_id: str) -> list[dict]:
        return await self._request("POST", "/my-keys", json={"user_id": user_id})

    async def create_api_key(
        self, user_id: str, label: str, custom_key: str | None = None
    ) -> dict:
        payload: dict = {"user_id": user_id, "label": label}
        if custom_key:
            payload["custom_key"] = custom_key
        return await self._request("POST", "/my-keys/create", json=payload)

    async def revoke_api_key(self, user_id: str, key_id: str) -> None:
        await self._request(
            "POST", "/my-keys/revoke", json={"user_id": user_id, "key_id": key_id}
        )

    async def request_guest_token(self, ip_address: str, user_agent: str | None = None) -> dict:
        url = f"{self.base_url}/api/guests/token"
        payload: dict = {"app_slug": "demo-assistant", "ip_address": ip_address}
        if user_agent:
            payload["user_agent"] = user_agent
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
        data = resp.json()
        if not resp.is_success:
            raise NexusError(resp.status_code, data.get("detail", "Guest login failed"))
        return data

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/health")
                return resp.status_code == 200
        except Exception:
            return False


def get_nexus_client() -> NexusClient:
    return NexusClient()
