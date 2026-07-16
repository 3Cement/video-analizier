"""Read-only LLM configuration helpers.

LLM provider, model and credentials are intentionally sourced only from server
environment variables. This compatibility module no longer persists overrides.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.llm.client import has_llm_credentials, llm_provider, resolve_model


def apply_llm_overrides(base: Settings) -> Settings:
    return base


def llm_status(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    provider = llm_provider(settings)
    openrouter_configured = bool(settings.openrouter_api_key.strip() or settings.cursor_api_key.strip())
    configured = {
        "openai": bool(settings.openai_api_key.strip()),
        "anthropic": bool(settings.anthropic_api_key.strip()),
        "openrouter": openrouter_configured,
        "cursor": openrouter_configured,
    }
    return {
        "provider": provider,
        "configured": configured,
        "has_credentials": has_llm_credentials(settings),
        "models": {
            "openai": settings.openai_model,
            "anthropic": settings.anthropic_model,
            "openrouter": resolve_model(settings) if provider == "openrouter" else settings.openrouter_model,
            "cursor": settings.cursor_model,
        },
        "base_urls": {
            "openai": settings.openai_base_url,
            "anthropic": settings.anthropic_base_url,
            "openrouter": settings.openrouter_base_url or settings.cursor_base_url,
            "cursor": settings.cursor_base_url,
        },
    }
