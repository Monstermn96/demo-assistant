from pydantic import BaseModel, Field


class ModelLoadConfigOut(BaseModel):
    context_length: int | None = None
    num_experts: int | None = None
    flash_attention: bool | None = None
    eval_batch_size: int | None = None
    offload_kv_cache_to_gpu: bool | None = None
    reasoning_effort: str | None = None
    keep_alive_interval_seconds: int | None = None
    max_concurrent_predictions: int | None = None


class ModelLoadConfigUpdate(BaseModel):
    context_length: int | None = Field(default=None, ge=256)
    num_experts: int | None = Field(default=None, ge=0)
    flash_attention: bool | None = None
    eval_batch_size: int | None = Field(default=None, ge=1)
    offload_kv_cache_to_gpu: bool | None = None
    reasoning_effort: str | None = None
    keep_alive_interval_seconds: int | None = Field(default=None, ge=0)
    max_concurrent_predictions: int | None = Field(default=None, ge=1)


class UserSettingsOut(BaseModel):
    default_model: str | None = None
    temperature: float = 0.7
    max_tokens: int = -1
    top_p: float = 1.0
    context_length: int | None = None
    chat_verbosity: str = "standard"
    chat_style: str = "bubbles"
    timezone: str | None = None
    model_load_config: ModelLoadConfigOut | None = None


class UserSettingsUpdate(BaseModel):
    default_model: str | None = Field(default=None)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=-1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    context_length: int | None = Field(default=None, ge=256)
    chat_verbosity: str | None = Field(default=None)
    chat_style: str | None = Field(default=None)
    timezone: str | None = Field(default=None)
    model_load_config: ModelLoadConfigUpdate | None = None
