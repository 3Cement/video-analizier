from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings

_STORE_NAME = "llm_settings.json"


def _store_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.data_dir / _STORE_NAME


def load_llm_overrides(settings: Settings | None = None) -> dict[str, Any]:
    path = _store_path(settings)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_llm_overrides(payload: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    settings.ensure_dirs()
    current = load_llm_overrides(settings)
    allowed = {
        "llm_provider",
        "openai_api_key",
        "openai_base_url",
        "openai_model",
        "anthropic_api_key",
        "anthropic_base_url",
        "anthropic_model",
        "cursor_api_key",
        "cursor_base_url",
        "cursor_model",
    }
    for key, value in payload.items():
        if key not in allowed:
            continue
        if value is None:
            continue
        text = str(value).strip()
        if text == "":
            current.pop(key, None)
        else:
            current[key] = text
    path = _store_path(settings)
    path.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return current


def apply_llm_overrides(base: Settings) -> Settings:
    overrides = load_llm_overrides(base)
    if not overrides:
        return base
    data = base.model_dump()
    for key, value in overrides.items():
        if key in data and value is not None:
            data[key] = value
    return Settings(**data)


def llm_status(settings: Settings | None = None) -> dict[str, Any]:
    settings = apply_llm_overrides(settings or get_settings())
    provider = (settings.llm_provider or "openai").strip().lower()
    configured = {
        "openai": bool(settings.openai_api_key.strip()),
        "anthropic": bool(settings.anthropic_api_key.strip()),
        "cursor": bool(settings.cursor_api_key.strip()),
    }
    return {
        "provider": provider,
        "configured": configured,
        "has_credentials": configured.get(provider, False),
        "models": {
            "openai": settings.openai_model,
            "anthropic": settings.anthropic_model,
            "cursor": settings.cursor_model,
        },
        "base_urls": {
            "openai": settings.openai_base_url,
            "anthropic": settings.anthropic_base_url,
            "cursor": settings.cursor_base_url,
        },
    }
