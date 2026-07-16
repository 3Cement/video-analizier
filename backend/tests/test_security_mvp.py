from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.config import get_settings
from app.models import User
from app.security import hash_password
from app.ssrf import validate_public_url


def test_ssrf_blocks_local_and_cloud_metadata():
    for url in ("http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data", "file:///etc/passwd"):
        try:
            validate_public_url(url)
        except ValueError:
            pass
        else:
            raise AssertionError(url)


def test_cookie_flags_and_no_login_token(client):
    settings = get_settings()
    settings.cookie_secure = True
    response = client.post("/api/auth/login", json={"email": "fixture@example.com", "password": "secret123"})
    assert response.status_code == 200
    assert "token" not in response.json()
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie


def test_csrf_rejects_missing_and_foreign_origin_in_production(client):
    settings = get_settings()
    settings.auth_required = True
    settings.public_base_url = "https://app.example.com"
    assert client.post("/api/auth/logout").status_code == 403
    assert client.post("/api/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/auth/logout", headers={"Origin": "https://app.example.com"}).status_code == 200


def test_verification_token_is_one_time(client):
    get_settings().single_user_email = "once@example.com"
    captured = {}
    with patch("app.api.auth_routes.verify_turnstile", return_value=True), patch(
        "app.api.auth_routes.send_verification_email", side_effect=lambda settings, email, token: captured.update(token=token)
    ):
        assert client.post("/api/auth/register", json={"email": "once@example.com", "password": "secret123", "turnstile_token": "ok"}).status_code == 200
    token = captured["token"]
    assert client.get("/api/auth/verify", params={"token": token}).status_code == 200
    assert client.get("/api/auth/verify", params={"token": token}).status_code == 400


def test_registration_is_limited_to_configured_email(client):
    settings = get_settings()
    settings.single_user_email = "Owner@Example.com"
    with patch("app.api.auth_routes.verify_turnstile") as turnstile:
        response = client.post(
            "/api/auth/register",
            json={"email": "other@example.com", "password": "secret123", "turnstile_token": "unused"},
        )
    assert response.status_code == 403
    assert response.json() == {"detail": "Registration is closed"}
    turnstile.assert_not_called()


def test_single_user_email_comparison_is_normalized(client):
    settings = get_settings()
    settings.single_user_email = " Owner@Example.com "
    with patch("app.api.auth_routes.verify_turnstile", return_value=True), patch(
        "app.api.auth_routes.send_verification_email"
    ):
        response = client.post(
            "/api/auth/register",
            json={"email": "owner@example.com", "password": "secret123", "turnstile_token": "ok"},
        )
    assert response.status_code == 200


def test_expired_reset_token_is_rejected(client, db_session):
    from app.security import hash_token
    user = User(email="expired@example.com", password_hash=hash_password("secret123"), token="expired-user",
                is_active=True, email_verified_at=datetime.now(timezone.utc), reset_token=hash_token("expired-reset"),
                reset_token_expires=datetime.now(timezone.utc) - timedelta(seconds=1))
    db_session.add(user)
    db_session.commit()
    response = client.post("/api/auth/password-reset/confirm", json={"token": "expired-reset", "new_password": "newpass123"})
    assert response.status_code == 400


def test_admin_requires_dedicated_key(client, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "dedicated-admin")
    get_settings.cache_clear()
    assert client.get("/api/admin/queue").status_code == 401
    assert client.get("/api/admin/queue", headers={"X-Admin-API-Key": "dedicated-admin"}).status_code == 200
