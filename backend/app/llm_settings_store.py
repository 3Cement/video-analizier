"""Read-only LLM configuration helpers.

LLM provider, model and credentials are intentionally sourced only from server
environment variables. This compatibility module no longer persists overrides.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings


def apply_llm_overrides(base: Settings) -> Settings:
    return base


def llm_status(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
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
