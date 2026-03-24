import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol, AsyncIterator, Any

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _lm_studio_native_base_url() -> str:
    """LM Studio server root (no /v1). Native API is at {base}/api/v1/..."""
    url = settings.lm_studio_url.rstrip("/")
    if url.endswith("/v1"):
        return url[:-3]
    return url


async def _lm_studio_native_request(
    method: str,
    path: str,
    json: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Call LM Studio native REST API (load, unload, list models)."""
    base = _lm_studio_native_base_url()
    url = f"{base}{path}"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.lm_studio_api_token:
        headers["Authorization"] = f"Bearer {settings.lm_studio_api_token}"
    async with httpx.AsyncClient(timeout=timeout or 60.0) as client:
        resp = await client.request(method, url, json=json, headers=headers)
        resp.raise_for_status()
        return resp.json() if resp.content else {}


_LOAD_CONFIG_KEYS = ("context_length", "num_experts", "flash_attention", "eval_batch_size", "offload_kv_cache_to_gpu", "max_concurrent_predictions")


@dataclass
class LoadedModelInfo:
    model_id: str
    instance_id: str
    model_type: str  # "llm" or "embedding"
    config: dict | None = None  # instance load_config from GET /api/v1/models


def _make_model_id(publisher: str, key: str, fallback: str = "unknown") -> str:
    """Build model identifier from native API fields without double-prefixing.

    Some models (e.g. HuggingFace-sourced) have the publisher already embedded
    in the key (``"qwen/qwen3.5-35b-a3b"``).  Blindly doing
    ``f"{publisher}/{key}"`` would produce ``"qwen/qwen/qwen3.5-35b-a3b"``.
    """
    if publisher and key:
        if key.startswith(f"{publisher}/"):
            return key
        return f"{publisher}/{key}"
    return key or fallback


async def _get_loaded_models() -> list[LoadedModelInfo]:
    """Query LM Studio for all currently loaded model instances."""
    try:
        data = await _lm_studio_native_request("GET", "/api/v1/models")
    except Exception as e:
        logger.warning("LM Studio native list failed: %s", e)
        return []
    result: list[LoadedModelInfo] = []
    for m in data.get("models") or []:
        publisher = m.get("publisher") or ""
        key = m.get("key") or ""
        model_id = _make_model_id(publisher, key, m.get("display_name", "unknown"))
        mtype = m.get("type", "llm")
        for inst in m.get("loaded_instances") or []:
            result.append(LoadedModelInfo(
                model_id=model_id,
                instance_id=inst.get("id", model_id),
                model_type=mtype,
                config=inst.get("config") or None,
            ))
    return result


async def list_models_native() -> list[dict]:
    """List models via LM Studio native GET /api/v1/models (full config, loaded_instances)."""
    try:
        data = await _lm_studio_native_request("GET", "/api/v1/models")
    except Exception as e:
        logger.warning("LM Studio native list failed: %s", e)
        return []
    models = data.get("models") or []
    result = []
    for m in models:
        publisher = m.get("publisher") or ""
        key = m.get("key") or ""
        model_id = _make_model_id(publisher, key, m.get("display_name", "unknown"))
        mtype = m.get("type", "llm")
        loaded = m.get("loaded_instances") or []
        first_config = loaded[0].get("config", {}) if loaded else {}
        load_config_schema = _load_config_schema_for_type(mtype, first_config)
        entry: dict = {
            "id": model_id,
            "key": key,
            "publisher": publisher,
            "display_name": m.get("display_name") or model_id,
            "type": mtype,
            "max_context_length": m.get("max_context_length"),
            "format": m.get("format"),
            "capabilities": m.get("capabilities"),
            "loaded_instances": loaded,
            "load_config_schema": load_config_schema,
        }
        result.append(entry)
    return result


def _load_config_matches(desired: dict[str, Any] | None, actual: dict | None) -> bool:
    """True if actual instance config matches desired (for keys present in desired).
    Treats missing key in actual as match to avoid reload loops when LM Studio omits it.
    Normalizes numeric and bool types for comparison.
    """
    if not desired:
        return True
    actual = actual or {}
    for key in _LOAD_CONFIG_KEYS:
        if key not in desired or desired[key] is None:
            continue
        actual_val = actual.get(key)
        if actual_val is None:
            continue
        desired_val = desired[key]
        if key in ("context_length", "num_experts", "eval_batch_size", "max_concurrent_predictions"):
            try:
                if int(actual_val) != int(desired_val):
                    return False
            except (TypeError, ValueError):
                if actual_val != desired_val:
                    return False
        elif key in ("flash_attention", "offload_kv_cache_to_gpu"):
            if bool(actual_val) != bool(desired_val):
                return False
        else:
            if actual_val != desired_val:
                return False
    return True


def _load_config_schema_for_type(mtype: str, instance_config: dict) -> dict:
    """Return which load options apply for this model type (for UI)."""
    schema: dict = {}
    if mtype == "llm":
        schema = {
            "context_length": {"min": 256, "max": instance_config.get("context_length") or 128000},
            "eval_batch_size": True,
            "flash_attention": True,
            "num_experts": True,
            "offload_kv_cache_to_gpu": True,
        }
    elif mtype == "embedding":
        schema = {
            "context_length": {"min": 256, "max": instance_config.get("context_length") or 8192},
        }
    return schema


def _normalize_load_config(load_config: dict[str, Any]) -> dict[str, Any]:
    """Coerce load_config values for LM Studio API (int/bool)."""
    out: dict[str, Any] = {}
    if load_config.get("context_length") is not None:
        try:
            out["context_length"] = int(load_config["context_length"])
        except (TypeError, ValueError):
            out["context_length"] = load_config["context_length"]
    if load_config.get("num_experts") is not None:
        try:
            out["num_experts"] = int(load_config["num_experts"])
        except (TypeError, ValueError):
            out["num_experts"] = load_config["num_experts"]
    if load_config.get("flash_attention") is not None:
        out["flash_attention"] = bool(load_config["flash_attention"])
    if load_config.get("eval_batch_size") is not None:
        try:
            out["eval_batch_size"] = int(load_config["eval_batch_size"])
        except (TypeError, ValueError):
            out["eval_batch_size"] = load_config["eval_batch_size"]
    if load_config.get("offload_kv_cache_to_gpu") is not None:
        out["offload_kv_cache_to_gpu"] = bool(load_config["offload_kv_cache_to_gpu"])
    if load_config.get("max_concurrent_predictions") is not None:
        try:
            out["max_concurrent_predictions"] = int(load_config["max_concurrent_predictions"])
        except (TypeError, ValueError):
            out["max_concurrent_predictions"] = load_config["max_concurrent_predictions"]
    return out


async def load_model(model: str, timeout: float | None = None, **load_config: Any) -> str | None:
    """Load a model via LM Studio native POST /api/v1/models/load. Returns instance_id or None.

    num_experts: Only has effect on MoE (Mixture of Experts) LLMs loaded by LM Studio's
    llama.cpp-based engine. See https://lmstudio.ai/docs/developer/rest/load

    max_concurrent_predictions: Not in the official REST load API yet; sent for future
    compatibility. Configure in LM Studio app (Developer > Server Settings) for now.
    """
    opts = _normalize_load_config(load_config)
    body: dict[str, Any] = {"model": model}
    if opts.get("context_length") is not None:
        body["context_length"] = opts["context_length"]
    if opts.get("num_experts") is not None:
        body["num_experts"] = opts["num_experts"]
    if opts.get("flash_attention") is not None:
        body["flash_attention"] = opts["flash_attention"]
    if opts.get("eval_batch_size") is not None:
        body["eval_batch_size"] = opts["eval_batch_size"]
    if opts.get("offload_kv_cache_to_gpu") is not None:
        body["offload_kv_cache_to_gpu"] = opts["offload_kv_cache_to_gpu"]
    if opts.get("max_concurrent_predictions") is not None:
        body["max_concurrent_predictions"] = opts["max_concurrent_predictions"]
    body["echo_load_config"] = True
    if len(body) > 2:
        logger.info("LM Studio load request: model=%s body=%s", model, body)
    try:
        data = await _lm_studio_native_request(
            "POST", "/api/v1/models/load", json=body,
            timeout=timeout or settings.model_load_timeout,
        )
        if data.get("load_config"):
            logger.info("LM Studio applied load_config: %s", data["load_config"])
        return data.get("instance_id")
    except Exception as e:
        logger.warning("LM Studio load model %s failed: %s", model, e)
        return None


async def unload_model(instance_id: str) -> None:
    """Unload a model via LM Studio native POST /api/v1/models/unload. Ignores errors."""
    try:
        await _lm_studio_native_request("POST", "/api/v1/models/unload", json={"instance_id": instance_id})
    except Exception as e:
        logger.debug("LM Studio unload %s failed (may already be unloaded): %s", instance_id, e)


class LLMProvider(Protocol):
    """Abstract interface for LLM backends (LM Studio, Ollama, etc.)."""

    async def chat(self, **kwargs) -> ChatCompletion: ...
    async def chat_stream(self, **kwargs) -> AsyncIterator: ...
    async def embed(self, text: str, model: str | None = None) -> list[float]: ...
    async def models(self) -> list[dict]: ...


class LMStudioProvider:
    """LM Studio backend via OpenAI-compatible API."""

    def __init__(self, base_url: str, timeout: float = 120.0):
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key="lm-studio",
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
        self.base_url = base_url

    async def chat(self, **kwargs) -> ChatCompletion:
        return await self._client.chat.completions.create(**kwargs)

    async def chat_stream(self, **kwargs):
        kwargs["stream"] = True
        return await self._client.chat.completions.create(**kwargs)

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        model = model or settings.embedding_model
        response = await self._client.embeddings.create(model=model, input=text)
        return response.data[0].embedding

    async def models(self) -> list[dict]:
        models = await self._client.models.list()
        result = []
        for m in models.data:
            entry: dict = {"id": m.id, "owned_by": m.owned_by}
            extra = getattr(m, "model_extra", None) or {}
            if "max_context_length" in extra:
                entry["max_context_length"] = extra["max_context_length"]
            if "loaded_instances" in extra:
                entry["loaded_instances"] = extra["loaded_instances"]
            result.append(entry)
        return result


class LLMClientManager:
    """Manages LLM providers with model lifecycle, retry/fallback, and separate LLM/embedding tracking."""

    _LOAD_RETRY_DELAY = 2.0

    def __init__(self):
        self.primary = LMStudioProvider(settings.lm_studio_url)
        self._fallbacks: list[LMStudioProvider] = []

        self._loaded_llm_id: str | None = None
        self._loaded_llm_instance_id: str | None = None

        self._loaded_embedding_id: str | None = None
        self._loaded_embedding_instance_id: str | None = None

        self._llm_lock = asyncio.Lock()
        self._embedding_lock = asyncio.Lock()
        self._keep_alive_task: asyncio.Task | None = None
        self._keep_alive_interval_seconds: int = 0

    def set_keep_alive_interval(self, seconds: int) -> None:
        """Set keep-alive interval (0 = disabled). Restarts the task if it is running."""
        self._keep_alive_interval_seconds = max(0, int(seconds))
        if self._keep_alive_task is not None:
            self._keep_alive_task.cancel()
            self._keep_alive_task = None
        if self._keep_alive_interval_seconds > 0:
            self._start_keep_alive_task()

    def add_fallback(self, base_url: str):
        self._fallbacks.append(LMStudioProvider(base_url))

    # ------------------------------------------------------------------
    # Ground-truth helpers
    # ------------------------------------------------------------------

    async def _sync_loaded_state(self) -> list[LoadedModelInfo]:
        """Query LM Studio and sync internal tracking with actual loaded state."""
        loaded = await _get_loaded_models()

        # Only clear state when we got a non-empty response and our model is missing.
        # Do not clear on empty list (transient API failure) to avoid mid-task reloads.
        loaded_llm_ids = {m.model_id for m in loaded if m.model_type == "llm"}
        loaded_emb_ids = {m.model_id for m in loaded if m.model_type == "embedding"}

        if self._loaded_llm_id and loaded_llm_ids and self._loaded_llm_id not in loaded_llm_ids:
            logger.info("LLM model %s no longer loaded in LM Studio (TTL/manual unload), clearing state", self._loaded_llm_id)
            self._loaded_llm_id = None
            self._loaded_llm_instance_id = None

        if self._loaded_embedding_id and loaded_emb_ids and self._loaded_embedding_id not in loaded_emb_ids:
            logger.info("Embedding model %s no longer loaded in LM Studio, clearing state", self._loaded_embedding_id)
            self._loaded_embedding_id = None
            self._loaded_embedding_instance_id = None

        return loaded

    # ------------------------------------------------------------------
    # LLM model lifecycle
    # ------------------------------------------------------------------

    async def _ensure_llm_loaded(self, model: str | None, load_config: dict[str, Any] | None) -> None:
        """Ensure the requested LLM model is loaded in LM Studio.

        Unloads any other LLM model first (but never touches embedding models).
        Retries once on failure, then raises RuntimeError.
        """
        if not model:
            return

        async with self._llm_lock:
            loaded = await self._sync_loaded_state()

            for info in loaded:
                if info.model_type == "llm" and info.model_id == model:
                    if self._loaded_llm_instance_id and info.instance_id == self._loaded_llm_instance_id:
                        return
                    if _load_config_matches(load_config, info.config):
                        self._loaded_llm_id = model
                        self._loaded_llm_instance_id = info.instance_id
                        return
                    logger.info("LLM model %s loaded with different config, re-loading with desired options",
                                model)
                    await unload_model(info.instance_id)
                    break

            for info in loaded:
                if info.model_type == "llm":
                    logger.info("Unloading LLM model %s (instance %s) to make room for %s",
                                info.model_id, info.instance_id, model)
                    await unload_model(info.instance_id)

            self._loaded_llm_id = None
            self._loaded_llm_instance_id = None

            opts = load_config or {}
            instance_id = await load_model(model, **opts)
            if instance_id is not None:
                self._loaded_llm_id = model
                self._loaded_llm_instance_id = instance_id
                logger.info("Loaded LLM model %s (instance %s)", model, instance_id)
                self._start_keep_alive_task()
                return

            logger.warning("First load attempt for %s failed, retrying in %.1fs...", model, self._LOAD_RETRY_DELAY)
            await asyncio.sleep(self._LOAD_RETRY_DELAY)
            instance_id = await load_model(model, **opts)
            if instance_id is not None:
                self._loaded_llm_id = model
                self._loaded_llm_instance_id = instance_id
                logger.info("Loaded LLM model %s on retry (instance %s)", model, instance_id)
                self._start_keep_alive_task()
                return

            raise RuntimeError(
                f"Failed to load model '{model}' in LM Studio after retries. "
                "Check that the model identifier is correct and LM Studio is running."
            )

    # ------------------------------------------------------------------
    # Embedding model lifecycle
    # ------------------------------------------------------------------

    async def _ensure_embedding_loaded(self, model: str | None) -> None:
        """Ensure the requested embedding model is loaded in LM Studio.

        Never unloads LLM models. Only unloads a different embedding model if one is loaded.
        """
        if not model:
            return

        async with self._embedding_lock:
            loaded = await self._sync_loaded_state()

            for info in loaded:
                if info.model_type == "embedding" and info.model_id == model:
                    self._loaded_embedding_id = model
                    self._loaded_embedding_instance_id = info.instance_id
                    return

            for info in loaded:
                if info.model_type == "embedding":
                    logger.info("Unloading embedding model %s (instance %s) to switch to %s",
                                info.model_id, info.instance_id, model)
                    await unload_model(info.instance_id)

            self._loaded_embedding_id = None
            self._loaded_embedding_instance_id = None

            instance_id = await load_model(model)
            if instance_id is not None:
                self._loaded_embedding_id = model
                self._loaded_embedding_instance_id = instance_id
                logger.info("Loaded embedding model %s (instance %s)", model, instance_id)
                return

            await asyncio.sleep(self._LOAD_RETRY_DELAY)
            instance_id = await load_model(model)
            if instance_id is not None:
                self._loaded_embedding_id = model
                self._loaded_embedding_instance_id = instance_id
                logger.info("Loaded embedding model %s on retry (instance %s)", model, instance_id)
                return

            logger.warning("Failed to load embedding model '%s'; embeddings will be unavailable", model)

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    async def ensure_ready(self, load_config: dict[str, Any] | None = None) -> None:
        """Pre-load the default LLM and embedding models at startup. Best-effort."""
        logger.info("Pre-loading default models...")
        try:
            await self._ensure_llm_loaded(settings.default_model, load_config)
        except RuntimeError as e:
            logger.warning("Startup LLM load failed (will retry on first request): %s", e)

        try:
            await self._ensure_embedding_loaded(settings.embedding_model)
        except Exception as e:
            logger.warning("Startup embedding load failed (will retry on first request): %s", e)

        self._start_keep_alive_task()

    def _start_keep_alive_task(self) -> None:
        """Start background keep-alive task if interval > 0 and not already running."""
        interval = self._keep_alive_interval_seconds or getattr(settings, "lm_studio_keep_alive_interval_seconds", 0) or 0
        if interval <= 0 or self._keep_alive_task is not None:
            return
        self._keep_alive_task = asyncio.create_task(self._keep_alive_loop(interval))
        logger.info("LM Studio keep-alive task started (interval=%ds)", interval)

    async def _keep_alive_loop(self, interval_seconds: float) -> None:
        """Periodically send a minimal chat request to reset LM Studio idle TTL.
        First sleep is capped at 5 minutes so the first ping happens before a 60-min TTL.
        """
        first_wait = min(interval_seconds, 300.0)
        try:
            await asyncio.sleep(first_wait)
        except asyncio.CancelledError:
            return
        while True:
            try:
                model = self._loaded_llm_id
                if model:
                    try:
                        await self.primary.chat(
                            model=model,
                            messages=[{"role": "user", "content": "."}],
                            max_tokens=1,
                        )
                    except Exception as e:
                        logger.debug("LM Studio keep-alive request failed: %s", e)
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("LM Studio keep-alive loop error: %s", e)

    # ------------------------------------------------------------------
    # Chat inference
    # ------------------------------------------------------------------

    async def chat(self, **kwargs) -> ChatCompletion:
        model = kwargs.get("model")
        load_config = kwargs.pop("load_config", None)
        await self._ensure_llm_loaded(model, load_config)
        providers = [self.primary, *self._fallbacks]
        last_err = None
        for provider in providers:
            try:
                return await provider.chat(**kwargs)
            except Exception as e:
                last_err = e
                logger.warning("LLM provider %s failed: %s", provider.base_url, e)
        raise last_err  # type: ignore[misc]

    async def chat_stream(self, **kwargs):
        model = kwargs.get("model")
        load_config = kwargs.pop("load_config", None)
        await self._ensure_llm_loaded(model, load_config)
        providers = [self.primary, *self._fallbacks]
        last_err = None
        for provider in providers:
            try:
                return await provider.chat_stream(**kwargs)
            except Exception as e:
                last_err = e
                logger.warning("LLM stream provider %s failed: %s", provider.base_url, e)
        raise last_err  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Embeddings (routed through manager for lifecycle)
    # ------------------------------------------------------------------

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        emb_model = model or settings.embedding_model
        await self._ensure_embedding_loaded(emb_model)
        return await self.primary.embed(text, model=emb_model)


llm_manager = LLMClientManager()

# Backwards-compatible module-level helpers
llm_client = llm_manager.primary._client


async def list_models() -> list[dict]:
    return await llm_manager.primary.models()


async def get_embedding(text: str) -> list[float]:
    return await llm_manager.embed(text)
