"""Villanyan-Agent 3.0 — Security: JWT tokens, password hashing, auth dependencies."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import get_db
from backend.core.models import RefreshToken, User

load_dotenv()

SECRET_KEY: str = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    import warnings
    warnings.warn("SECRET_KEY is not set! Using ephemeral key.")
    import secrets
    SECRET_KEY = secrets.token_hex(32)

ALLOWED_ALGORITHMS = frozenset({"HS256", "HS384", "HS512"})
ALGORITHM: str = os.getenv("ALGORITHM", "HS256").upper()
if ALGORITHM not in ALLOWED_ALGORITHMS:
    raise ValueError(f"ALGORITHM={ALGORITHM!r} not allowed: {sorted(ALLOWED_ALGORITHMS)}")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))

bearer_scheme = HTTPBearer(auto_error=False)
limiter = Limiter(key_func=get_remote_address)
rate_limit_login = limiter.limit("10/minute")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "type": "access", "exp": expire,
               "iat": datetime.now(UTC), "jti": uuid.uuid4().hex}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def create_refresh_token(user_id: int, db: AsyncSession) -> str:
    expire = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire,
               "iat": datetime.now(UTC), "jti": uuid.uuid4().hex}
    token_str = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    token_hash = sha256(token_str.encode()).hexdigest()
    db.add(RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expire))
    await db.flush()
    return token_str


def verify_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=list(ALLOWED_ALGORITHMS),
                             options={"require": ["exp", "sub", "type", "iat", "jti"]})
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.PyJWTError:
        return None


def verify_refresh_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=list(ALLOWED_ALGORITHMS),
                             options={"require": ["exp", "sub", "type", "iat", "jti"]})
        if payload.get("type") != "refresh":
            return None
        return payload
    except jwt.PyJWTError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization")
    payload = verify_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user
