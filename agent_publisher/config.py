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

    # Skills auth: email whitelist (comma-separated) and admin emails (comma-separated)
    email_whitelist: str = ""
    admin_emails: str = ""

    # Runtime-added admins (not persisted to .env, managed via API)
    _runtime_admins: set[str] = set()

    # Server
    host: str = "0.0.0.0"
    port: int = 9099
    debug: bool = False

    # Public-facing server host for display (WeChat IP whitelist, guide page, etc.)
    # Can be a domain (e.g. "publisher.example.com") or IP (e.g. "1.2.3.4").
    # If empty, auto-detected from outbound socket.
    server_host: str = ""

    def get_jwt_secret(self) -> str:
        return self.jwt_secret or f"jwt-{self.access_key}-secret"

    def get_server_host(self) -> str:
        """Return the public-facing server host (domain or IP).

        Priority:
          1. Explicit ``server_host`` from .env / environment variable ``SERVER_HOST``
          2. Legacy ``server_ip`` env var (backward compat)
          3. Auto-detect outbound IP via UDP socket
        """
        if self.server_host:
            return self.server_host
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def get_email_whitelist(self) -> set[str]:
        """Return the set of whitelisted emails (lowered)."""
        if not self.email_whitelist.strip():
            return set()
        return {e.strip().lower() for e in self.email_whitelist.split(",") if e.strip()}

    def get_admin_emails(self) -> set[str]:
        """Return the set of admin emails (lowered), including runtime-added ones."""
        admins: set[str] = set()
        if self.admin_emails.strip():
            admins = {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}
        admins |= self._runtime_admins
        return admins

    def is_email_allowed(self, email: str) -> bool:
        """Check if an email is in the whitelist (admins are always allowed)."""
        email_lower = email.strip().lower()
        return email_lower in self.get_email_whitelist() or email_lower in self.get_admin_emails()

    def is_admin(self, email: str) -> bool:
        """Check if an email is an admin."""
        return email.strip().lower() in self.get_admin_emails()

    def add_admin(self, email: str) -> None:
        """Add an admin at runtime (not persisted to .env)."""
        email_lower = email.strip().lower()
        self._runtime_admins.add(email_lower)

    def remove_admin(self, email: str) -> bool:
        """Remove a runtime-added admin. Returns True if removed, False if not found."""
        email_lower = email.strip().lower()
        if email_lower in self._runtime_admins:
            self._runtime_admins.discard(email_lower)
            return True
        return False

    def list_admins(self) -> dict:
        """List all admins categorized by source."""
        env_admins: set[str] = set()
        if self.admin_emails.strip():
            env_admins = {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}
        return {
            "env_admins": sorted(env_admins),
            "runtime_admins": sorted(self._runtime_admins),
            "all_admins": sorted(self.get_admin_emails()),
        }


settings = Settings()
