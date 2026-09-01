"""
Cravin — Application Configuration
Loads settings from .env file with sensible defaults.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # App
    app_name: str = "Cravin"
    app_env: str = "development"
    debug: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./cravin.db"

    # JWT Auth
    jwt_secret_key: str = "change-me-to-a-random-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # OpenAI (blank = mock mode)
    openai_api_key: str = ""

    # Razorpay (mocked in Phase 1)
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # Google Maps
    google_maps_api_key: str = ""

    @property
    def is_ai_mock_mode(self) -> bool:
        """When no API key is set, AI customizer returns pre-written responses."""
        return not self.openai_api_key

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
