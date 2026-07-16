import argparse
import io
from datetime import timezone

from sqlalchemy import select

from app.cli import cmd_provision_user
from app.config import get_settings
from app.models import User
from app.security import verify_password


def test_provision_user_creates_active_verified_single_user(db_session, monkeypatch):
    settings = get_settings()
    settings.single_user_email = "owner@example.com"
    monkeypatch.setattr("sys.stdin", io.StringIO("strong-test-password\n"))

    result = cmd_provision_user(
        argparse.Namespace(email="", password_stdin=True)
    )

    assert result == 0
    user = db_session.scalar(select(User).where(User.email == "owner@example.com"))
    assert user is not None
    assert user.is_active is True
    assert user.email_verified_at is not None
    assert user.email_verified_at.replace(tzinfo=timezone.utc).tzinfo is not None
    assert verify_password("strong-test-password", user.password_hash)


def test_provision_user_rejects_email_outside_single_user_setting(db_session, monkeypatch):
    settings = get_settings()
    settings.single_user_email = "owner@example.com"
    monkeypatch.setattr("sys.stdin", io.StringIO("strong-test-password\n"))

    try:
        cmd_provision_user(
            argparse.Namespace(email="other@example.com", password_stdin=True)
        )
    except SystemExit as exc:
        assert str(exc) == "Email must match SINGLE_USER_EMAIL"
    else:
        raise AssertionError("Expected mismatched email to be rejected")
