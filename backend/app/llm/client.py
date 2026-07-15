from __future__ import annotations

from typing import Optional

import httpx
from openai import OpenAI

from app.config import Settings, get_settings


def llm_provider(settings: Settings) -> str:
    return (settings.llm_provider or "openai").strip().lower()


def has_llm_credentials(settings: Optional[Settings] = None) -> bool:
    settings = settings or get_settings()
    provider = llm_provider(settings)
    if provider == "anthropic":
        return bool(settings.anthropic_api_key.strip())
    if provider == "cursor":
        return bool(settings.cursor_api_key.strip())
    return bool(settings.openai_api_key.strip())


def resolve_model(settings: Settings) -> str:
    provider = llm_provider(settings)
    if provider == "anthropic":
        return settings.anthropic_model
    if provider == "cursor":
        return settings.cursor_model
    return settings.openai_model


def get_openai_compatible_client(settings: Settings) -> tuple[OpenAI, str]:
    provider = llm_provider(settings)
    if provider == "cursor":
        if not settings.cursor_api_key.strip():
            raise RuntimeError(
                "CURSOR_API_KEY is not set. Configure .env or UI settings to enable LLM."
            )
        client = OpenAI(
            api_key=settings.cursor_api_key,
            base_url=settings.cursor_base_url or "https://api.openai.com/v1",
        )
        return client, settings.cursor_model
    if not settings.openai_api_key.strip():
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Configure .env or UI settings to enable LLM."
        )
    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    return client, settings.openai_model


def _anthropic_completion(
    system: str,
    user: str,
    settings: Settings,
    temperature: float,
) -> str:
    if not settings.anthropic_api_key.strip():
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Configure .env or UI settings to enable LLM."
        )
    base = settings.anthropic_base_url.rstrip("/")
    url = f"{base}/v1/messages"
    payload = {
        "model": settings.anthropic_model,
        "max_tokens": 4096,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    parts = data.get("content") or []
    texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
    return "\n".join(t for t in texts if t).strip()


def chat_completion(
    system: str,
    user: str,
    settings: Optional[Settings] = None,
    temperature: float = 0.2,
) -> str:
    settings = settings or get_settings()
    provider = llm_provider(settings)

    if provider == "anthropic":
        return _anthropic_completion(system, user, settings, temperature)

    client, model = get_openai_compatible_client(settings)
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = response.choices[0].message.content or ""
    return content.strip()
