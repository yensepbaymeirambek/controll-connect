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

    # Jira, reached through an MCP server speaking streamable HTTP.
    jira_mcp_url: str = ""
    jira_mcp_tool: str = "jira_search"
    jira_mcp_token: str = ""
    jira_jql: str = "ORDER BY updated DESC"
    jira_limit: int = 100
    jira_timeout: float = 30.0
    # Used to build issue links; the MCP server may not return them.
    jira_base_url: str = ""

    # Seconds a fetched record set is reused before hitting the MCP server again.
    records_cache_ttl: float = 60.0

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_enabled(self) -> bool:
        """Without a key, chat and dashboard generation are unavailable."""
        return bool(self.openai_api_key)

    @property
    def jira_enabled(self) -> bool:
        return bool(self.jira_mcp_url)

    @property
    def jira_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.jira_mcp_token}"} if self.jira_mcp_token else {}


@lru_cache
def get_settings() -> Settings:
    return Settings()
