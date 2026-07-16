from datetime import datetime, timezone
from unittest.mock import patch

from app.ingest.youtube import expand_youtube_urls
from app.models import User
from app.security import hash_password, hash_token, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert hashed.startswith("$argon2id$")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_register_verify_login_and_search(client, db_session):
    from app.config import get_settings

    get_settings().single_user_email = "a@example.com"
    sent = {}
    with patch("app.api.auth_routes.verify_turnstile", return_value=True), patch(
        "app.api.auth_routes.send_verification_email",
        side_effect=lambda settings, email, token: sent.update(token=token),
    ):
        reg = client.post("/api/auth/register", json={"email": "a@example.com", "password": "secret123", "turnstile_token": "ok"})
    assert reg.status_code == 200
    assert "token" not in reg.json()
    verify = client.get("/api/auth/verify", params={"token": sent["token"]})
    assert verify.status_code == 200
    assert "token" not in verify.json()
    assert "HttpOnly" in verify.headers["set-cookie"]

    text = client.post("/api/sources/text", json={"title": "Protein guide", "text": "Eat more protein every day for recovery.", "auto_summarize": False})
    assert text.status_code == 200
    assert "user_id" not in text.json()


def test_unverified_user_cannot_login(client, db_session):
    db_session.add(User(email="pending@example.com", password_hash=hash_password("secret123"), token="pending", is_active=False))
    db_session.commit()
    result = client.post("/api/auth/login", json={"email": "pending@example.com", "password": "secret123"})
    assert result.status_code == 403


def test_expand_youtube_urls_passthrough():
    urls = expand_youtube_urls(["https://www.youtube.com/watch?v=abcdefghijk"])
    assert urls == ["https://www.youtube.com/watch?v=abcdefghijk"]
