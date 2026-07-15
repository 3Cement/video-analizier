from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User


def get_optional_user_id(
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> str:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()

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
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    settings = get_settings()
    required = settings.api_key.strip()
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()

    if settings.auth_required and not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not required and not settings.auth_required:
        # Open mode: allow anonymous; optional user tokens still accepted elsewhere.
        return

    if required and token and token == required:
        return
    if token and db.scalar(select(User).where(User.token == token)) is not None:
        return
    if required:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    if settings.auth_required:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
