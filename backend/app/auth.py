from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from app.config import get_settings


def get_optional_user_id(x_user_id: Optional[str] = Header(default=None)) -> str:
    return (x_user_id or "anonymous").strip() or "anonymous"


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    settings = get_settings()
    required = settings.api_key.strip()
    if not required:
        return
    if not x_api_key or x_api_key.strip() != required:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
