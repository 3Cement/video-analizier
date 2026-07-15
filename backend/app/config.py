from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "openai"  # openai | anthropic | cursor

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-sonnet-4-20250514"

    cursor_api_key: str = ""
    cursor_base_url: str = "https://api.openai.com/v1"
    cursor_model: str = "gpt-4o-mini"

    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_language: str = "pl"

    data_dir: Path = Path("./data")
    database_url: str = "sqlite:///./data/app.db"
    media_dir: Path = Path("./data/media")
    ytdlp_cookies: str = ""
    ytdlp_proxy: str = ""
    ytdlp_max_retries: int = 3
    ytdlp_retry_backoff_seconds: float = 2.0

    api_key: str = ""
    max_video_duration_seconds: int = 7200
    max_audio_duration_seconds: int = 21600
    daily_source_limit: int = 50
    worker_mode: bool = False
    worker_poll_seconds: float = 3.0
    job_max_workers: int = 2
    captions_first: bool = False
    max_summary_chunks: int = 6
    public_base_url: str = ""

    host: str = "0.0.0.0"
    port: int = 8000

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings