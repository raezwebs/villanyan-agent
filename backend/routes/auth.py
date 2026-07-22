"""Villanyan-Agent 3.0 — Auth routes."""

import os
import secrets
from datetime import UTC, datetime
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import get_db
from backend.core.models import RefreshToken, User
from backend.core.schemas import LoginRequest, RefreshRequest, TokenResponse, MessageResponse, UserOut
from backend.core.security import (
    create_access_token, create_refresh_token, get_current_user,
    hash_password, rate_limit_login, verify_password, verify_refresh_token,
)
from backend.routes.settings import _write_env_key

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Password from env, with fallback
_VILLANYAN_PASSWORD: str = os.getenv("VILLANYAN_PASSWORD", "")
if not _VILLANYAN_PASSWORD:
    import warnings
    warnings.warn("VILLANYAN_PASSWORD not set! Using random ephemeral password.")
    _VILLANYAN_PASSWORD = secrets.token_urlsafe(16)


@router.post("/login")
@rate_limit_login
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate — password-only or username+password."""
    if not body.username:
        # Password-only mode
        if body.password == _VILLANYAN_PASSWORD:
            result = await db.execute(select(User).where(User.role == "admin"))
            user = result.scalar_one_or_none()
            if not user:
                result = await db.execute(select(User).limit(1))
                user = result.scalar_one_or_none()
            if not user:
                user = User(username="admin", password_hash=hash_password(_VILLANYAN_PASSWORD), role="admin")
                db.add(user)
                await db.flush()
            user.last_login = datetime.now(UTC)
            await db.flush()
            access = create_access_token(user.id, user.role)
            refresh = await create_refresh_token(user.id, db)
            return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}
        raise HTTPException(status_code=401, detail="Nieprawidłowe hasło")

    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user.last_login = datetime.now(UTC)
    await db.flush()
    access = create_access_token(user.id, user.role)
    refresh = await create_refresh_token(user.id, db)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = verify_refresh_token(body.refresh_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    token_hash = sha256(body.refresh_token.encode()).hexdigest()
    result = await db.execute(select(RefreshToken).where(
        RefreshToken.token_hash == token_hash, RefreshToken.revoked == False))
    stored = result.scalar_one_or_none()
    if stored is None:
        raise HTTPException(status_code=401, detail="Refresh token revoked")
    stored.revoked = True
    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    access = create_access_token(user.id, user.role)
    new_refresh = await create_refresh_token(user.id, db)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.post("/logout", response_model=MessageResponse)
async def logout(body: RefreshRequest, user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_db)):
    token_hash = sha256(body.refresh_token.encode()).hexdigest()
    result = await db.execute(select(RefreshToken).where(
        RefreshToken.token_hash == token_hash, RefreshToken.revoked == False))
    stored = result.scalar_one_or_none()
    if stored:
        stored.revoked = True
    return MessageResponse(detail="Logged out")


@router.get("/check")
async def auth_check(user: User = Depends(get_current_user)):
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password")
async def change_password(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the VILLANYAN_PASSWORD. Requires old password."""
    old = body.get("old_password", "")
    new_pass = body.get("new_password", "")
    if not new_pass or len(new_pass) < 4:
        raise HTTPException(status_code=400, detail="Hasło min. 4 znaki")
    if not old or old != _VILLANYAN_PASSWORD:
        raise HTTPException(status_code=403, detail="Nieprawidłowe stare hasło")
    _write_env_key("VILLANYAN_PASSWORD", new_pass)
    # Update DB hash
    user.password_hash = hash_password(new_pass)
    await db.flush()
    return {"status": "ok", "message": "Hasło zmienione — zaloguj się ponownie"}
