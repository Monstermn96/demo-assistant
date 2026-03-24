import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth.security import decode_token
from app.db.database import get_db
from app.db.models import User
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_user_flexible(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Auth that accepts either a user JWT or a service API key with identity headers.

    Service auth requires:
      - Authorization: Bearer <service_api_key>
      - X-Nexus-Identity-Id: <nexus identity UUID>
      - X-Nexus-Display-Name: <display name for auto-created users>
    """
    token = credentials.credentials

    if settings.service_api_key and token == settings.service_api_key:
        identity_id = request.headers.get("x-nexus-identity-id", "")
        display_name = request.headers.get("x-nexus-display-name", "")
        if not identity_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service auth requires X-Nexus-Identity-Id header",
            )
        user = await _resolve_identity(db, identity_id, display_name)
        return user

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def _resolve_identity(
    db: AsyncSession, identity_id: str, display_name: str
) -> User:
    """Map a Nexus identity_id to a local ARIM user, auto-creating if needed."""
    result = await db.execute(select(User).where(User.nexus_id == identity_id))
    user = result.scalar_one_or_none()
    if user:
        return user

    username = display_name.lower().replace(" ", "_")[:50] if display_name else f"user_{identity_id[:8]}"

    result = await db.execute(select(User).where(User.username == username))
    existing = result.scalar_one_or_none()
    if existing:
        if not existing.nexus_id:
            existing.nexus_id = identity_id
            await db.flush()
        return existing

    user = User(
        nexus_id=identity_id,
        username=username,
        hashed_password="nexus-managed",
    )
    db.add(user)
    await db.flush()
    logger.info("Auto-created ARIM user '%s' for Nexus identity %s", username, identity_id)
    return user
