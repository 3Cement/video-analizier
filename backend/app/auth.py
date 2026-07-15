from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User


def _extract_token(
    request: Request,
    authorization: Optional[str],
    x_api_key: Optional[str],
) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    cookie = request.cookies.get("va_session")
    if cookie and cookie.strip():
        return cookie.strip()
    return None


def get_optional_user_id(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> str:
    token = _extract_token(request, authorization, x_api_key)
    if token:
        settings = get_settings()
        if settings.api_key and token == settings.api_key.strip():
            return (x_user_id or "anonymous").strip() or "anonymous"
        user = db.scalar(select(User).where(User.token == token))
        if user is not None:
            return f"user:{user.id}"

    settings = get_settings()
    if settings.auth_required:
        raise HTTPException(status_code=401, detail="Authentication required")
    return (x_user_id or "anonymous").strip() or "anonymous"


def verify_api_key(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    settings = get_settings()
    required = settings.api_key.strip()
    token = _extract_token(request, authorization, x_api_key)

    if settings.auth_required and not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not required and not settings.auth_required:
        return

    if required and token and token == required:
        return
    if token and db.scalar(select(User).where(User.token == token)) is not None:
        return
    if required:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    if settings.auth_required:
        raise HTTPException(status_code=401, detail="Invalid or missing token")


def require_admin_api_key(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> None:
    settings = get_settings()
    required = settings.api_key.strip()
    if not required:
        # Open admin stats in local/dev when no API key is configured.
        return
    token = _extract_token(request, authorization, x_api_key)
    if token != required:
        raise HTTPException(status_code=401, detail="Admin API key required")
