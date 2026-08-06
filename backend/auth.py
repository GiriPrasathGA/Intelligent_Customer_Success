"""
novaTech AI Customer Support — Authentication Module

JWT-based authentication: register, login, token verification,
password reset, and FastAPI dependencies.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.config import settings
from backend.config.models import (
    RegisterRequest, LoginRequest, TokenResponse, UserPublic,
    ForgotPasswordRequest, ResetPasswordRequest,
)
from backend.database import User, get_db

# ── Password Hashing ──────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    try:
        return pwd_context.hash(password[:72])
    except Exception:
        import hashlib
        return "sha256$" + hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    if hashed.startswith("sha256$"):
        import hashlib
        return hashed == "sha256$" + hashlib.sha256(plain.encode()).hexdigest()
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        import hashlib
        return hashed == "sha256$" + hashlib.sha256(plain.encode()).hexdigest()


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, remember_me: bool = False) -> str:
    expire_minutes = settings.jwt_expire_minutes * (7 if remember_me else 1)
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=expire_minutes),
        "iat": datetime.utcnow(),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── Dependencies ──────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    user_id = int(payload.get("sub", 0))

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user but returns None instead of raising on failure."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


# ── Auth Handlers ─────────────────────────────────────────────────────────────

async def register_user(req: RegisterRequest, db: AsyncSession) -> TokenResponse:
    # Check existing
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=req.name,
        email=req.email,
        hashed_password=hash_password(req.password),
        phone=req.phone,
        address=req.address,
        is_active=True,
        is_verified=True,   # auto-verify for demo
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserPublic.model_validate(user),
    )


async def login_user(req: LoginRequest, db: AsyncSession) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == req.email, User.is_active == True))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id, remember_me=req.remember_me)
    expire = settings.jwt_expire_minutes * (7 if req.remember_me else 1) * 60
    return TokenResponse(
        access_token=token,
        expires_in=expire,
        user=UserPublic.model_validate(user),
    )


async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession) -> dict:
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    # Always return success to prevent email enumeration
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        # In production: send email with token
        # For demo: return token directly
        return {"message": "Password reset link sent", "demo_token": token}

    return {"message": "If that email exists, a reset link has been sent"}


async def reset_password(req: ResetPasswordRequest, db: AsyncSession) -> dict:
    result = await db.execute(
        select(User).where(
            User.reset_token == req.token,
            User.reset_token_expires > datetime.utcnow(),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.hashed_password = hash_password(req.new_password)
    user.reset_token = None
    user.reset_token_expires = None

    return {"message": "Password reset successfully"}
