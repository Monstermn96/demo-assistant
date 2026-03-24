from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError
from app.config import get_settings

settings = get_settings()

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: int, nexus_session: str | None = None) -> str:
    data = {"sub": str(user_id), "type": "access"}
    if nexus_session:
        data["nexus_session"] = nexus_session
    return create_token(data, timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(user_id: int, nexus_session: str | None = None) -> str:
    data = {"sub": str(user_id), "type": "refresh"}
    if nexus_session:
        data["nexus_session"] = nexus_session
    return create_token(data, timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None
