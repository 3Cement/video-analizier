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
    database_url: str = "postgresql+psycopg://video_analizier:video_analizier@localhost:5432/video_analizier"
    media_dir: Path = Path("./data/media")
    ytdlp_cookies: str = ""
    ytdlp_proxy: str = ""
    ytdlp_max_retries: int = 3
    ytdlp_retry_backoff_seconds: float = 2.0

    api_key: str = ""
    max_video_duration_seconds: int = 3600
    max_audio_duration_seconds: int = 7200
    daily_source_limit: int = 3
    daily_youtube_limit: int = 30
    daily_audio_limit: int = 20
    daily_article_limit: int = 40
    auth_required: bool = True
    cookie_secure: bool = False
    allowed_origins: str = ""
    trusted_proxy_ips: str = ""
    admin_api_key: str = ""
    resend_api_key: str = ""
    resend_from_email: str = ""
    turnstile_secret_key: str = ""
    turnstile_site_key: str = ""
    verification_ttl_seconds: int = 3600
    daily_question_limit: int = 10
    global_daily_llm_limit: int = 1000
    max_upload_bytes: int = 100 * 1024 * 1024
    max_text_bytes: int = 1024 * 1024
    session_max_age_seconds: int = 60 * 60 * 24 * 30
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 300
    register_rate_limit: int = 5
    register_rate_window_seconds: int = 3600
    job_max_attempts: int = 3
    job_stale_seconds: int = 1800
    job_retry_base_seconds: float = 5.0
    password_reset_ttl_seconds: int = 3600
    worker_mode: bool = False
    worker_poll_seconds: float = 3.0
    job_max_workers: int = 2
    captions_first: bool = False
    max_summary_chunks: int = 6
    public_base_url: str = ""

    @property
    def allowed_origin_list(self) -> list[str]:
        return [value.strip().rstrip("/") for value in self.allowed_origins.split(",") if value.strip()]

    @property
    def trusted_proxy_ip_set(self) -> set[str]:
        return {value.strip() for value in self.trusted_proxy_ips.split(",") if value.strip()}

    host: str = "0.0.0.0"
    port: int = 8000

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def validate_production(self) -> None:
        if not self.auth_required:
            return
        required = {
            "PUBLIC_BASE_URL": self.public_base_url,
            "ADMIN_API_KEY": self.admin_api_key,
            "RESEND_API_KEY": self.resend_api_key,
            "RESEND_FROM_EMAIL": self.resend_from_email,
            "TURNSTILE_SITE_KEY": self.turnstile_site_key,
            "TURNSTILE_SECRET_KEY": self.turnstile_secret_key,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise RuntimeError(f"Missing required production settings: {', '.join(missing)}")
        if not any((self.openai_api_key, self.anthropic_api_key, self.cursor_api_key)):
            raise RuntimeError("At least one server-side LLM API key is required")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
