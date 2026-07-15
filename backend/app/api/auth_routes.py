from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.ratelimit import enforce_rate_limit
from app.schemas import (
    AuthLoginRequest,
    AuthOut,
    AuthRegisterRequest,
    PasswordResetConfirm,
    PasswordResetOut,
    PasswordResetRequest,
)
from app.security import hash_password, new_api_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key="va_session",
        value=token,
        httponly=True,
        secure=bool(settings.cookie_secure),
        samesite="lax",
        max_age=settings.session_max_age_seconds,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie("va_session", path="/")


def _auth_out(user: User) -> AuthOut:
    return AuthOut(email=user.email, token=user.token, user_id=f"user:{user.id}")


@router.post("/register", response_model=AuthOut)
def register(
    payload: AuthRegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthOut:
    settings = get_settings()
    email = payload.email.strip().lower()
    enforce_rate_limit(
        f"register:{_client_ip(request)}",
        limit=settings.register_rate_limit,
        window_seconds=settings.register_rate_window_seconds,
        detail="Too many registration attempts. Try again later.",
    )
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(payload.password), token=new_api_token())
    db.add(user)
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, user.token)
    return _auth_out(user)


@router.post("/login", response_model=AuthOut)
def login(
    payload: AuthLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthOut:
    settings = get_settings()
    email = payload.email.strip().lower()
    ip = _client_ip(request)
    enforce_rate_limit(
        f"login:{ip}:{email}",
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window_seconds,
        detail="Too many login attempts. Try again later.",
    )
    enforce_rate_limit(
        f"login-ip:{ip}",
        limit=settings.login_rate_limit * 3,
        window_seconds=settings.login_rate_window_seconds,
        detail="Too many login attempts from this IP.",
    )
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.token:
        user.token = new_api_token()
        db.commit()
        db.refresh(user)
    _set_session_cookie(response, user.token)
    return _auth_out(user)


@router.post("/logout")
def logout(response: Response) -> dict:
    _clear_session_cookie(response)
    return {"ok": True}


@router.post("/password-reset/request", response_model=PasswordResetOut)
def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetOut:
    settings = get_settings()
    email = payload.email.strip().lower()
    enforce_rate_limit(
        f"reset:{_client_ip(request)}:{email}",
        limit=5,
        window_seconds=3600,
        detail="Too many password reset requests.",
    )
    user = db.scalar(select(User).where(User.email == email))
    # Always succeed to avoid email enumeration.
    if user is None:
        return PasswordResetOut(ok=True)
    token = new_api_token()
    user.reset_token = token
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(
        seconds=settings.password_reset_ttl_seconds
    )
    db.commit()
    base = (settings.public_base_url or "").rstrip("/")
    link = f"{base}/?reset_token={quote(token)}" if base else f"/?reset_token={quote(token)}"
    return PasswordResetOut(ok=True, reset_token=token, reset_link=link)


@router.post("/password-reset/confirm", response_model=AuthOut)
def password_reset_confirm(
    payload: PasswordResetConfirm,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthOut:
    token = payload.token.strip()
    user = db.scalar(select(User).where(User.reset_token == token))
    if user is None or user.reset_token_expires is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    expires = user.reset_token_expires
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user.password_hash = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.token = new_api_token()
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, user.token)
    return _auth_out(user)
