from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import client_ip, get_current_user
from app.config import get_settings
from app.db import get_db
from app.email_service import send_password_reset_email, send_verification_email
from app.models import User
from app.ratelimit import enforce_rate_limit
from app.schemas import (
    AuthLoginRequest, AuthOut, AuthRegisterRequest, PasswordResetConfirm,
    PasswordResetOut, PasswordResetRequest, RegisterOut, ResendVerificationRequest,
)
from app.security import hash_password, hash_token, new_api_token, verify_password
from app.turnstile import verify_turnstile

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
def auth_config() -> dict[str, str]:
    return {"turnstile_site_key": get_settings().turnstile_site_key}


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie("va_session", token, httponly=True, secure=settings.cookie_secure,
                        samesite="lax", max_age=settings.session_max_age_seconds, path="/")


def _issue_verification(db: Session, user: User) -> str:
    settings = get_settings()
    token = new_api_token()
    user.verification_token_hash = hash_token(token)
    user.verification_token_expires = datetime.now(timezone.utc) + timedelta(seconds=settings.verification_ttl_seconds)
    db.commit()
    return token


def _not_expired(value: datetime | None) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value >= datetime.now(timezone.utc)


@router.post("/register", response_model=RegisterOut)
def register(payload: AuthRegisterRequest, request: Request, db: Session = Depends(get_db)) -> RegisterOut:
    settings = get_settings()
    ip = client_ip(request)
    enforce_rate_limit(db, f"register:{ip}", limit=settings.register_rate_limit,
                       window_seconds=settings.register_rate_window_seconds,
                       detail="Too many registration attempts. Try again later.")
    email = payload.email.strip().lower()
    if settings.single_user_email.strip().lower() != email:
        raise HTTPException(status_code=403, detail="Registration is closed")
    if not verify_turnstile(settings, payload.turnstile_token, ip):
        raise HTTPException(status_code=400, detail="Turnstile verification failed")
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(payload.password), token=new_api_token(), is_active=False)
    db.add(user)
    db.flush()
    token = _issue_verification(db, user)
    try:
        send_verification_email(settings, email, token)
    except Exception:
        db.delete(user)
        db.commit()
        raise HTTPException(status_code=503, detail="Verification email could not be sent")
    return RegisterOut()


@router.get("/verify", response_model=AuthOut)
def verify_email(token: str, response: Response, db: Session = Depends(get_db)) -> AuthOut:
    user = db.scalar(select(User).where(User.verification_token_hash == hash_token(token.strip())))
    if user is None or not _not_expired(user.verification_token_expires):
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user.is_active = True
    user.email_verified_at = datetime.now(timezone.utc)
    user.verification_token_hash = None
    user.verification_token_expires = None
    user.token = new_api_token()
    db.commit()
    _set_session_cookie(response, user.token)
    return AuthOut(email=user.email)


@router.post("/resend-verification", response_model=PasswordResetOut)
def resend_verification(payload: ResendVerificationRequest, request: Request, db: Session = Depends(get_db)) -> PasswordResetOut:
    settings = get_settings()
    enforce_rate_limit(db, f"verify:{client_ip(request)}:{payload.email.lower()}", limit=5,
                       window_seconds=3600, detail="Too many requests")
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if user is not None and not user.is_active:
        token = _issue_verification(db, user)
        send_verification_email(settings, user.email, token)
    return PasswordResetOut(ok=True)


@router.post("/login", response_model=AuthOut)
def login(payload: AuthLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthOut:
    settings = get_settings()
    email = payload.email.strip().lower()
    ip = client_ip(request)
    enforce_rate_limit(db, f"login:{ip}:{email}", limit=settings.login_rate_limit,
                       window_seconds=settings.login_rate_window_seconds, detail="Too many login attempts")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active or user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Email verification required")
    user.token = new_api_token()
    db.commit()
    _set_session_cookie(response, user.token)
    return AuthOut(email=user.email)


@router.get("/me", response_model=AuthOut)
def me(user: User = Depends(get_current_user)) -> AuthOut:
    return AuthOut(email=user.email)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie("va_session", path="/")
    return {"ok": True}


@router.post("/password-reset/request", response_model=PasswordResetOut)
def password_reset_request(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)) -> PasswordResetOut:
    settings = get_settings()
    email = payload.email.strip().lower()
    enforce_rate_limit(db, f"reset:{client_ip(request)}:{email}", limit=5, window_seconds=3600, detail="Too many requests")
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.is_active:
        token = new_api_token()
        user.reset_token = hash_token(token)
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(seconds=settings.password_reset_ttl_seconds)
        db.commit()
        try:
            send_password_reset_email(settings, email, token)
        except Exception:
            pass  # response remains neutral; operational failure is logged by the mail provider path
    return PasswordResetOut(ok=True)


@router.post("/password-reset/confirm", response_model=AuthOut)
def password_reset_confirm(payload: PasswordResetConfirm, response: Response, db: Session = Depends(get_db)) -> AuthOut:
    user = db.scalar(select(User).where(User.reset_token == hash_token(payload.token.strip())))
    if user is None or not _not_expired(user.reset_token_expires):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user.password_hash = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.token = new_api_token()
    db.commit()
    _set_session_cookie(response, user.token)
    return AuthOut(email=user.email)
