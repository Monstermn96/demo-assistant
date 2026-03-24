from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from zoneinfo import available_timezones

from app.config import get_settings
from app.db.database import get_db
from app.db.models import User, UserSettings, GlobalSettings
from app.auth.middleware import get_current_user
from app.settings.models import UserSettingsOut, UserSettingsUpdate, ModelLoadConfigOut
from app.llm.client import llm_manager

router = APIRouter(prefix="/settings", tags=["settings"])
_settings = get_settings()


async def get_or_create_settings(db: AsyncSession, user_id: int) -> UserSettings:
    """Return the user's settings row, creating one with defaults if it doesn't exist."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        await db.flush()
    return settings


async def get_or_create_global_settings(db: AsyncSession) -> GlobalSettings:
    """Return the single global settings row, creating it if missing."""
    result = await db.execute(select(GlobalSettings).where(GlobalSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = GlobalSettings(id=1)
        db.add(row)
        await db.flush()
    return row


def global_load_config_from_row(global_row: GlobalSettings) -> dict | None:
    """Build load_config dict from global settings (only non-None). Used at startup and for chat."""
    d: dict = {}
    if global_row.context_length is not None:
        d["context_length"] = global_row.context_length
    if global_row.num_experts is not None:
        d["num_experts"] = global_row.num_experts
    if global_row.flash_attention is not None:
        d["flash_attention"] = global_row.flash_attention
    if global_row.eval_batch_size is not None:
        d["eval_batch_size"] = global_row.eval_batch_size
    if global_row.offload_kv_cache_to_gpu is not None:
        d["offload_kv_cache_to_gpu"] = global_row.offload_kv_cache_to_gpu
    if global_row.max_concurrent_predictions is not None:
        d["max_concurrent_predictions"] = global_row.max_concurrent_predictions
    return d if d else None


def get_effective_default_model(
    user_default: str | None,
    global_default: str | None,
) -> str | None:
    """Resolve effective default model: user override > global > config."""
    return user_default or global_default or _settings.default_model or None


@router.get("", response_model=UserSettingsOut)
async def get_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await get_or_create_settings(db, user.id)
    global_row = await get_or_create_global_settings(db)
    effective_model = get_effective_default_model(
        settings.default_model,
        global_row.default_model,
    )
    load_config_out = ModelLoadConfigOut(
        context_length=global_row.context_length,
        num_experts=global_row.num_experts,
        flash_attention=global_row.flash_attention,
        eval_batch_size=global_row.eval_batch_size,
        offload_kv_cache_to_gpu=global_row.offload_kv_cache_to_gpu,
        reasoning_effort=global_row.reasoning_effort,
        keep_alive_interval_seconds=global_row.keep_alive_interval_seconds,
        max_concurrent_predictions=global_row.max_concurrent_predictions,
    ) if (global_row.context_length is not None or global_row.num_experts is not None
            or global_row.flash_attention is not None or global_row.eval_batch_size is not None
            or global_row.offload_kv_cache_to_gpu is not None or global_row.reasoning_effort
            or global_row.keep_alive_interval_seconds is not None or global_row.max_concurrent_predictions is not None) else None

    return UserSettingsOut(
        default_model=effective_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
        context_length=settings.context_length,
        chat_verbosity=settings.chat_verbosity or "standard",
        chat_style=settings.chat_style or "bubbles",
        timezone=settings.timezone,
        model_load_config=load_config_out,
    )


@router.put("", response_model=UserSettingsOut)
async def update_settings(
    body: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await get_or_create_settings(db, user.id)
    global_row = await get_or_create_global_settings(db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "default_model":
            settings.default_model = value
        elif field == "model_load_config":
            if value is not None and isinstance(value, dict):
                for k in ("context_length", "num_experts", "flash_attention", "eval_batch_size", "offload_kv_cache_to_gpu", "reasoning_effort", "keep_alive_interval_seconds", "max_concurrent_predictions"):
                    if k in value:
                        setattr(global_row, k, value[k])
        elif field == "timezone":
            tz_value = value if value and value.strip() else None
            if tz_value is not None and tz_value not in available_timezones():
                raise HTTPException(status_code=400, detail=f"Invalid timezone: {tz_value}")
            settings.timezone = tz_value
        else:
            setattr(settings, field, value)

    await db.flush()

    keep_alive = global_row.keep_alive_interval_seconds if global_row.keep_alive_interval_seconds is not None else getattr(_settings, "lm_studio_keep_alive_interval_seconds", 0) or 0
    llm_manager.set_keep_alive_interval(keep_alive)

    effective_model = get_effective_default_model(
        settings.default_model,
        global_row.default_model,
    )
    load_config_out = ModelLoadConfigOut(
        context_length=global_row.context_length,
        num_experts=global_row.num_experts,
        flash_attention=global_row.flash_attention,
        eval_batch_size=global_row.eval_batch_size,
        offload_kv_cache_to_gpu=global_row.offload_kv_cache_to_gpu,
        reasoning_effort=global_row.reasoning_effort,
        keep_alive_interval_seconds=global_row.keep_alive_interval_seconds,
        max_concurrent_predictions=global_row.max_concurrent_predictions,
    ) if (global_row.context_length is not None or global_row.num_experts is not None
            or global_row.flash_attention is not None or global_row.eval_batch_size is not None
            or global_row.offload_kv_cache_to_gpu is not None or global_row.reasoning_effort
            or global_row.keep_alive_interval_seconds is not None or global_row.max_concurrent_predictions is not None) else None

    return UserSettingsOut(
        default_model=effective_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
        context_length=settings.context_length,
        chat_verbosity=settings.chat_verbosity or "standard",
        chat_style=settings.chat_style or "bubbles",
        timezone=settings.timezone,
        model_load_config=load_config_out,
    )
