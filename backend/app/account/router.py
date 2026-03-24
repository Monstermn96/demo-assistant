import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.middleware import get_current_user
from app.auth.nexus_client import NexusClient, NexusError, get_nexus_client
from app.db.models import User
from app.account.models import ApiKeyCreate, ApiKeyCreated, ApiKeyOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/account", tags=["account"])


def _require_nexus_id(user: User) -> str:
    if not user.nexus_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is not linked to Nexus identity",
        )
    return user.nexus_id


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    user: User = Depends(get_current_user),
    nexus: NexusClient = Depends(get_nexus_client),
):
    nexus_id = _require_nexus_id(user)
    try:
        keys = await nexus.list_api_keys(nexus_id)
    except NexusError as e:
        logger.error("Nexus list-keys failed: %s", e.detail)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not fetch API keys")

    return [
        ApiKeyOut(
            id=str(k["id"]),
            key_prefix=k["key_prefix"],
            label=k["label"],
            created_at=k["created_at"],
            last_used_at=k.get("last_used_at"),
        )
        for k in keys
        if not k.get("revoked_at")
    ]


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    user: User = Depends(get_current_user),
    nexus: NexusClient = Depends(get_nexus_client),
):
    nexus_id = _require_nexus_id(user)
    try:
        result = await nexus.create_api_key(nexus_id, body.label, body.custom_key)
    except NexusError as e:
        if e.status_code == 409:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.detail)
        logger.error("Nexus create-key failed: %s", e.detail)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not create API key")

    return ApiKeyCreated(
        id=str(result["id"]),
        api_key=result["api_key"],
        key_prefix=result["key_prefix"],
        label=result["label"],
    )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str,
    user: User = Depends(get_current_user),
    nexus: NexusClient = Depends(get_nexus_client),
):
    nexus_id = _require_nexus_id(user)
    try:
        await nexus.revoke_api_key(nexus_id, key_id)
    except NexusError as e:
        if e.status_code == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        logger.error("Nexus revoke-key failed: %s", e.detail)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not revoke API key")
