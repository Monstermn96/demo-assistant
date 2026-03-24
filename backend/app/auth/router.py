import re
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from app.db.database import get_db
from app.db.models import User
from app.auth.security import (
    hash_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.auth.nexus_client import NexusClient, NexusError, get_nexus_client

router = APIRouter(prefix="/auth", tags=["auth"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{2,16}$")


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError("Username must be 2-16 characters: letters, numbers, underscores only")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


async def _get_or_create_local_user(
    db: AsyncSession, nexus_id: str, username: str
) -> User:
    result = await db.execute(select(User).where(User.nexus_id == nexus_id))
    user = result.scalar_one_or_none()
    if user:
        if user.username != username:
            user.username = username
            await db.flush()
        return user

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user and not user.nexus_id:
        user.nexus_id = nexus_id
        await db.flush()
        return user

    user = User(
        nexus_id=nexus_id,
        username=username,
        hashed_password="nexus-managed",
    )
    db.add(user)
    await db.flush()
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    nexus: NexusClient = Depends(get_nexus_client),
):
    try:
        result = await nexus.login(body.username, body.password)
    except NexusError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from e

    user = await _get_or_create_local_user(db, result["user_id"], result["username"])
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id, nexus_session=result["session_token"]),
        refresh_token=create_refresh_token(user.id, nexus_session=result["session_token"]),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    nexus: NexusClient = Depends(get_nexus_client),
):
    try:
        result = await nexus.register(body.username, body.password)
    except NexusError as e:
        if e.status_code == 409:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken") from e
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Registration failed") from e

    user = await _get_or_create_local_user(db, result["user_id"], result["username"])
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id, nexus_session=result["session_token"]),
        refresh_token=create_refresh_token(user.id, nexus_session=result["session_token"]),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    nexus: NexusClient = Depends(get_nexus_client),
):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    nexus_session = payload.get("nexus_session")
    if nexus_session:
        identity = await nexus.validate_session(nexus_session)
        if not identity:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nexus session expired")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user.id, nexus_session=nexus_session),
        refresh_token=create_refresh_token(user.id, nexus_session=nexus_session),
    )


async def _get_or_create_guest_user(db: AsyncSession, ip_address: str) -> User:
    guest_id = "guest-" + hashlib.sha256(ip_address.encode()).hexdigest()[:12]
    result = await db.execute(select(User).where(User.nexus_id == guest_id))
    user = result.scalar_one_or_none()
    if user:
        return user
    username = "guest_" + hashlib.sha256(ip_address.encode()).hexdigest()[:8]
    result2 = await db.execute(select(User).where(User.username == username))
    user = result2.scalar_one_or_none()
    if user:
        if not user.nexus_id:
            user.nexus_id = guest_id
            await db.flush()
        return user
    user = User(nexus_id=guest_id, username=username, hashed_password="guest-session")
    db.add(user)
    await db.flush()
    return user


@router.post("/guest", response_model=TokenResponse)
async def guest_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    nexus: NexusClient = Depends(get_nexus_client),
):
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "127.0.0.1")
    user_agent = request.headers.get("user-agent")
    try:
        await nexus.request_guest_token(ip, user_agent)
    except NexusError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e

    user = await _get_or_create_guest_user(db, ip)
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/setup", status_code=201)
async def setup_admin(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    nexus: NexusClient = Depends(get_nexus_client),
):
    """One-time admin user creation. Kept for backwards compatibility."""
    try:
        nexus_result = await nexus.register(body.username, body.password)
    except NexusError as e:
        if e.status_code == 409:
            try:
                nexus_result = await nexus.login(body.username, body.password)
            except NexusError:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already taken",
                ) from e
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Registration failed: {e.detail}",
            ) from e

    user = await _get_or_create_local_user(db, nexus_result["user_id"], nexus_result["username"])
    await db.commit()
    return {"message": "User created", "user_id": user.id}
