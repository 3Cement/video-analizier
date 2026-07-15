from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import AuthLoginRequest, AuthOut, AuthRegisterRequest
from app.security import hash_password, new_api_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut)
def register(payload: AuthRegisterRequest, db: Session = Depends(get_db)) -> AuthOut:
    email = payload.email.strip().lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(payload.password), token=new_api_token())
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthOut(email=user.email, token=user.token, user_id=f"user:{user.id}")


@router.post("/login", response_model=AuthOut)
def login(payload: AuthLoginRequest, db: Session = Depends(get_db)) -> AuthOut:
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.token:
        user.token = new_api_token()
        db.commit()
        db.refresh(user)
    return AuthOut(email=user.email, token=user.token, user_id=f"user:{user.id}")
