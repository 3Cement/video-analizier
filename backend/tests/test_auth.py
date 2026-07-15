from app.models import Source


def test_api_key_required(client, db_session, monkeypatch):
    from app.config import get_settings
    from app.main import create_app
    from app.db import get_db

    get_settings.cache_clear()
    monkeypatch.setenv("API_KEY", "secret-key")
    get_settings.cache_clear()

    app = create_app()

    def _override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db

    from fastapi.testclient import TestClient

    with TestClient(app) as authed_client:
        denied = authed_client.get("/api/sources")
        assert denied.status_code == 401

        allowed = authed_client.get("/api/sources", headers={"X-API-Key": "secret-key"})
        assert allowed.status_code == 200

    app.dependency_overrides.clear()
    get_settings.cache_clear()
