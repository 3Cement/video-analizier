from __future__ import annotations

from typing import Optional

from openai import OpenAI

from app.config import Settings, get_settings


def get_openai_client(settings: Optional[Settings] = None) -> OpenAI:
    settings = settings or get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Configure .env to enable summarization and Q&A."
        )
    return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)


def chat_completion(
    system: str,
    user: str,
    settings: Optional[Settings] = None,
    temperature: float = 0.2,
) -> str:
    settings = settings or get_settings()
    client = get_openai_client(settings)
    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = response.choices[0].message.content or ""
    return content.strip()