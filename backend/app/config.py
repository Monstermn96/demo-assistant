from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "DemoAssistant"
    debug: bool = False
    port: int = 3093

    # LM Studio
    lm_studio_url: str = "http://192.168.1.20:1234/v1"
    lm_studio_api_token: str = ""  # Optional Bearer token for native load/unload/list API
    default_model: str = "mistralai/magistral-small-2509"
    embedding_model: str = "text-embedding-nomic-embed-text-v1.5"
    model_load_timeout: int = 120  # seconds for native API model load requests
    lm_studio_keep_alive_interval_seconds: int = 0  # 0 = disabled; e.g. 1800 to ping every 30 min to avoid idle TTL unload

    # TTS Service
    tts_url: str = "http://localhost:4123"
    tts_enabled: bool = False

    # Memory Service
    memory_url: str = "http://localhost:3092"
    memory_enabled: bool = True
    memory_api_key: str = ""

    # Nexus identity management
    nexus_url: str = "http://localhost:3086"
    nexus_api_key: str = ""

    # Auth
    service_api_key: str = ""
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    admin_password: str = "admin"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/demo-assistant.db"

    # Cloudflare Access
    cf_access_team: str = ""
    cf_access_aud: str = ""

    # File manager sandboxed directories
    sandboxed_dirs: list[str] = []

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
