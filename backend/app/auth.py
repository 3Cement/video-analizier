from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User


def _session_token(request: Request) -> str | None:
    value = request.cookies.get("va_session")
    return value.strip() if value and value.strip() else None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _session_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = db.scalar(select(User).where(User.token == token))
    if user is None or not user.is_active or user.email_verified_at is None:
        raise HTTPException(status_code=401, detail="Active verified account required")
    return user


def get_optional_user_id(user: User = Depends(get_current_user)) -> str:
    return f"user:{user.id}"


def verify_api_key(user: User = Depends(get_current_user)) -> None:
    return None


def require_admin_api_key(x_admin_api_key: str | None = Header(default=None)) -> None:
    required = get_settings().admin_api_key.strip()
    if not required or x_admin_api_key != required:
        raise HTTPException(status_code=401, detail="Admin API key required")


def client_ip(request: Request) -> str:
    direct = request.client.host if request.client else "unknown"
    if direct in get_settings().trusted_proxy_ip_set:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded
    return direct
