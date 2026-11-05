"""Application configuration and paths."""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RMC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Storage paths
    data_dir: Path = Path("./data")

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8099
    log_level: str = "INFO"

    # Background sync settings
    sync_interval_seconds: int = 120
    max_concurrent_downloads: int = 6

    # Security
    app_password: str = ""
    mcp_bearer_token: str = ""

    # Vision & OCR Settings
    gemini_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("RMC_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("RMC_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    openai_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("RMC_OPENAI_BASE_URL", "OPENAI_BASE_URL"),
    )
    vision_provider: str = Field(
        default="gemini",
        validation_alias=AliasChoices("RMC_VISION_PROVIDER", "VISION_PROVIDER"),
    )
    vision_model: str = Field(
        default="gemini-flash-lite-latest",
        validation_alias=AliasChoices("RMC_VISION_MODEL", "VISION_MODEL", "GEMINI_MODEL"),
    )

    # reMarkable Cloud endpoints (overrideable for tests or proxying)
    rm_auth_host: str = "https://webapp-prod.cloud.remarkable.engineering"
    rm_sync_host: str = "https://internal.cloud.remarkable.com"
    rm_connect_host: str = "https://my.remarkable.com"
    rm_device_desc: str = "desktop-linux"

    @property
    def blobs_dir(self) -> Path:
        p = self.data_dir / "blobs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cache_dir(self) -> Path:
        p = self.data_dir / "cache"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def secrets_dir(self) -> Path:
        p = self.data_dir / "secrets"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_dir(self) -> Path:
        p = self.data_dir / "db"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_path(self) -> Path:
        return self.db_dir / "library.db"

    @property
    def tokens_file(self) -> Path:
        return self.secrets_dir / "tokens.json"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def set_settings(settings: Settings) -> None:
    global _settings
    _settings = settings
