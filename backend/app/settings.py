from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from the environment or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Comma-separated list of browser origins allowed to call the API directly.
    cors_origins: str = "http://localhost:5173"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # Set to target an OpenAI-compatible gateway instead of api.openai.com.
    openai_base_url: str = ""
    openai_timeout: float = 30.0

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_enabled(self) -> bool:
        """Without a key the API stays in local mode and returns a canned answer."""
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
