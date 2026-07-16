from __future__ import annotations

import httpx

from app.config import Settings


def verify_turnstile(settings: Settings, token: str, remote_ip: str) -> bool:
    if not settings.turnstile_secret_key:
        return not settings.auth_required  # explicit local-development escape hatch
    try:
        response = httpx.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": settings.turnstile_secret_key, "response": token, "remoteip": remote_ip},
            timeout=10.0,
        )
        response.raise_for_status()
        return bool(response.json().get("success"))
    except (httpx.HTTPError, ValueError):
        return False
