from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database (supports PostgreSQL or SQLite for dev)
    database_url: str = "sqlite+aiosqlite:///agent_publisher.db"

    # Tencent Cloud
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""

    # Default LLM
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4o"
    default_llm_api_key: str = ""
    default_llm_base_url: str = ""

    # Access key for UI and API authentication
    access_key: str = "agent-publisher-2024"

    # JWT secret (derived from access_key by default)
    jwt_secret: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 9099
    debug: bool = False

    def get_jwt_secret(self) -> str:
        return self.jwt_secret or f"jwt-{self.access_key}-secret"


settings = Settings()
