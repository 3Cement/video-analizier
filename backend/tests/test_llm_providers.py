from unittest.mock import MagicMock, patch

from app.config import Settings
from app.llm.client import chat_completion, has_llm_credentials
from app.llm_settings_store import apply_llm_overrides


def test_has_llm_credentials_per_provider():
    assert has_llm_credentials(Settings(llm_provider="openai", openai_api_key="k"))
    assert has_llm_credentials(Settings(llm_provider="anthropic", anthropic_api_key="k"))
    assert has_llm_credentials(Settings(llm_provider="cursor", cursor_api_key="k"))
    assert not has_llm_credentials(Settings(llm_provider="anthropic", openai_api_key="k"))


def test_anthropic_chat_completion():
    settings = Settings(
        llm_provider="anthropic",
        anthropic_api_key="ant-key",
        anthropic_model="claude-test",
    )
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "Odpowiedź Claude"}]
    }
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.post.return_value = mock_response

    with patch("app.llm.client.httpx.Client", return_value=mock_client):
        out = chat_completion("sys", "user", settings=settings)

    assert out == "Odpowiedź Claude"
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert args[0].endswith("/v1/messages")
    assert kwargs["headers"]["x-api-key"] == "ant-key"


def test_cursor_uses_openai_compatible(monkeypatch):
    settings = Settings(
        llm_provider="cursor",
        cursor_api_key="cursor-key",
        cursor_base_url="https://example.com/v1",
        cursor_model="gpt-test",
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Cursor reply"))]
    )
    with patch("app.llm.client.OpenAI", return_value=fake_client) as openai_cls:
        out = chat_completion("sys", "user", settings=settings)
    assert out == "Cursor reply"
    openai_cls.assert_called_once_with(api_key="cursor-key", base_url="https://example.com/v1")


def test_llm_settings_api_and_override(client, db_session, tmp_path, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    status = client.get("/api/llm/status")
    assert status.status_code == 200
    assert status.json()["provider"] in {"openai", "anthropic", "cursor"}

    saved = client.put(
        "/api/llm/settings",
        json={
            "llm_provider": "anthropic",
            "anthropic_api_key": "sk-ant-test",
            "anthropic_model": "claude-test",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["provider"] == "anthropic"
    assert body["configured"]["anthropic"] is True

    settings = apply_llm_overrides(get_settings())
    assert settings.llm_provider == "anthropic"
    assert settings.anthropic_api_key == "sk-ant-test"
    get_settings.cache_clear()
