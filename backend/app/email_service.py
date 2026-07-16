from __future__ import annotations

import httpx

from app.config import Settings


def send_email(settings: Settings, *, to: str, subject: str, html: str) -> None:
    if not settings.resend_api_key or not settings.resend_from_email:
        raise RuntimeError("Resend is not configured")
    response = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={"from": settings.resend_from_email, "to": [to], "subject": subject, "html": html},
        timeout=15.0,
    )
    response.raise_for_status()


def send_verification_email(settings: Settings, email: str, token: str) -> None:
    base = settings.public_base_url.rstrip("/")
    link = f"{base}/api/auth/verify?token={token}"
    send_email(settings, to=email, subject="Potwierdź adres e-mail", html=f'<p><a href="{link}">Potwierdź konto</a>. Link wygasa za godzinę.</p>')


def send_password_reset_email(settings: Settings, email: str, token: str) -> None:
    base = settings.public_base_url.rstrip("/")
    link = f"{base}/?reset_token={token}"
    send_email(settings, to=email, subject="Reset hasła", html=f'<p><a href="{link}">Ustaw nowe hasło</a>. Link wygasa za godzinę.</p>')
