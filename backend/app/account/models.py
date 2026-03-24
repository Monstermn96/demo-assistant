from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    custom_key: str | None = Field(
        default=None,
        min_length=16,
        max_length=128,
        description="User-supplied key string (min 16 chars). Auto-generated if omitted.",
    )


class ApiKeyOut(BaseModel):
    id: str
    key_prefix: str
    label: str
    created_at: str
    last_used_at: str | None = None


class ApiKeyCreated(BaseModel):
    id: str
    api_key: str
    key_prefix: str
    label: str
