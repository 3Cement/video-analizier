from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models import Source
from app.pipeline import _fail_source
from app.ratelimit import clear_rate_limits, enforce_rate_limit
from app.worker import claim_next_pending, reclaim_stale_jobs
from fastapi import HTTPException
import pytest

from app.config import Settings


def test_login_rate_limit(client, db_session, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "login_rate_limit", 3)
    monkeypatch.setattr(settings, "login_rate_window_seconds", 600)
    from app.models import User
    from app.security import hash_password
    from datetime import datetime, timezone
    db_session.add(User(email="rate@example.com", password_hash=hash_password("secret123"), token="rate", is_active=True, email_verified_at=datetime.now(timezone.utc)))
    db_session.commit()
    for _ in range(3):
        res = client.post("/api/auth/login", json={"email": "rate@example.com", "password": "wrongpass"})
        assert res.status_code in {401, 429}
    blocked = client.post("/api/auth/login", json={"email": "rate@example.com", "password": "wrongpass"})
    assert blocked.status_code == 429
    get_settings.cache_clear()


def test_password_reset_flow(client, db_session):
    from app.config import get_settings
    from app.models import User
    from app.security import hash_password
    from datetime import datetime, timezone
    db_session.add(User(email="reset@example.com", password_hash=hash_password("secret123"), token="reset", is_active=True, email_verified_at=datetime.now(timezone.utc)))
    db_session.commit()
    settings = get_settings()
    settings.resend_api_key = "test-resend-key"
    settings.resend_from_email = "sender@example.com"
    captured = {}
    with patch("app.api.auth_routes.send_password_reset_email", side_effect=lambda settings, email, token: captured.update(token=token)):
        req = client.post("/api/auth/password-reset/request", json={"email": "reset@example.com"})
    assert req.status_code == 200
    assert "reset_token" not in req.json()
    token = captured["token"]
    conf = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "new_password": "newpass123"},
    )
    assert conf.status_code == 200
    assert "va_session" in conf.cookies
    bad = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "secret123"})
    assert bad.status_code == 401
    good = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "newpass123"})
    assert good.status_code == 200


def test_session_cookie_auth(client):
    listed = client.get("/api/sources")
    assert listed.status_code == 200


def test_fail_source_schedules_retry(db_session):
    source = Source(source_type="text", title="T", status="downloading", user_id="anonymous", attempts=1, max_attempts=3)
    db_session.add(source)
    db_session.commit()
    _fail_source(db_session, source.id, RuntimeError("connection timed out"))
    db_session.refresh(source)
    assert source.status == "pending"
    assert source.next_run_at is not None
    assert source.error_code == "network"


def test_fail_source_terminal_when_attempts_exhausted(db_session):
    source = Source(source_type="text", title="T", status="downloading", user_id="anonymous", attempts=3, max_attempts=3)
    db_session.add(source)
    db_session.commit()
    _fail_source(db_session, source.id, RuntimeError("connection timed out"))
    db_session.refresh(source)
    assert source.status == "failed"


def test_reclaim_stale_and_claim(db_session, monkeypatch):
    monkeypatch.setenv("JOB_STALE_SECONDS", "60")
    from app.config import get_settings

    get_settings.cache_clear()
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    stuck = Source(
        source_type="text",
        title="Stuck",
        status="downloading",
        user_id="anonymous",
        claimed_at=old,
        attempts=1,
    )
    pending = Source(source_type="text", title="P", status="pending", user_id="anonymous")
    db_session.add_all([stuck, pending])
    db_session.commit()
    assert reclaim_stale_jobs(db_session) >= 1
    db_session.refresh(stuck)
    assert stuck.status == "pending"
    claimed = claim_next_pending(db_session)
    assert claimed is not None
    assert claimed.status == "downloading"
    assert claimed.attempts >= 1
    get_settings.cache_clear()


def test_admin_queue(client, db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ADMIN_API_KEY", "admin-secret")
    get_settings.cache_clear()
    db_session.add(Source(source_type="text", title="Q", status="pending", user_id="anonymous"))
    db_session.commit()
    res = client.get("/api/admin/queue", headers={"X-Admin-API-Key": "admin-secret"})
    assert res.status_code == 200
    assert res.json()["pending"] >= 1


def test_enforce_rate_limit_unit(db_session):
    clear_rate_limits(db_session)
    enforce_rate_limit(db_session, "k", limit=2, window_seconds=60, detail="nope")
    enforce_rate_limit(db_session, "k", limit=2, window_seconds=60, detail="nope")
    with pytest.raises(HTTPException) as exc:
        enforce_rate_limit(db_session, "k", limit=2, window_seconds=60, detail="nope")
    assert exc.value.status_code == 429
    clear_rate_limits(db_session)


def test_single_user_email_is_required_in_production():
    settings = Settings(
        auth_required=True,
        public_base_url="https://project.vercel.app",
        admin_api_key="admin",
        resend_api_key="resend",
        resend_from_email="onboarding@resend.dev",
        turnstile_site_key="site",
        turnstile_secret_key="secret",
        openrouter_api_key="openrouter",
        single_user_email="",
    )

    with pytest.raises(RuntimeError, match="SINGLE_USER_EMAIL"):
        settings.validate_production()

    settings.single_user_email = "owner@example.com"
    settings.validate_production()


def test_email_services_are_optional_when_self_registration_is_disabled():
    settings = Settings(
        auth_required=True,
        self_registration_enabled=False,
        public_base_url="https://video-analizier.vercel.app",
        admin_api_key="admin",
        single_user_email="owner@example.com",
        openrouter_api_key="openrouter",
        resend_api_key="",
        resend_from_email="",
        turnstile_site_key="",
        turnstile_secret_key="",
    )

    settings.validate_production()


def test_local_ollama_needs_no_paid_api_key_in_production():
    settings = Settings(
        auth_required=True,
        self_registration_enabled=False,
        public_base_url="https://video-analizier.vercel.app",
        admin_api_key="admin",
        single_user_email="owner@example.com",
        llm_provider="ollama",
        ollama_base_url="http://ollama:11434/v1",
        ollama_model="qwen3:4b-instruct",
        openai_api_key="",
        anthropic_api_key="",
        openrouter_api_key="",
        cursor_api_key="",
    )

    settings.validate_production()
