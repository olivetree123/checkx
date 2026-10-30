from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgres://checkx:checkx_local@localhost:5432/checkx"
    storage_dir: Path = Path("./data/uploads")
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
    ]
    cookie_secure: bool = False
    session_days: int = Field(default=7, ge=1, le=90)
    max_upload_mb: int = Field(default=20, ge=1, le=100)
    max_image_pixels: int = Field(default=40_000_000, ge=1)
    auto_create_schema: bool = False


settings = Settings()
TORTOISE_ORM = {
    "connections": {"default": settings.database_url},
    "apps": {
        "models": {
            "models": ["app.models"],
            "default_connection": "default",
            "migrations": "app.migrations",
        }
    },
    "use_tz": True,
    "timezone": "UTC",
}
