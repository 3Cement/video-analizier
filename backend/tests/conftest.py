import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("CURSOR_API_KEY", "")


@pytest.fixture()
def db_session(tmp_path: Path):
    os.environ["DATA_DIR"] = str(tmp_path / "data")
    os.environ["MEDIA_DIR"] = str(tmp_path / "media")
    os.environ["DATABASE_URL"] = "sqlite://"

    from app.config import get_settings
    from app.db import Base, configure_engine

    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    configure_engine("sqlite://", poolclass=StaticPool)
    # Rebind using the same StaticPool in-memory engine for shared state
    from app import db as db_module

    db_module.engine = engine
    db_module.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    Base.metadata.create_all(bind=engine)
    session = db_module.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        get_settings.cache_clear()


@pytest.fixture()
def client(db_session):
    from datetime import datetime, timezone
    from app.auth import get_optional_user_id
    from app.db import get_db
    from app.main import create_app
    from app.models import User
    from app.security import hash_password

    user = User(email="fixture@example.com", password_hash=hash_password("secret123"), token="fixture-session", is_active=True, email_verified_at=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    app = create_app()

    def _override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_optional_user_id] = lambda: "anonymous"
    with TestClient(app) as test_client:
        test_client.cookies.set("va_session", "fixture-session")
        yield test_client
    app.dependency_overrides.clear()
