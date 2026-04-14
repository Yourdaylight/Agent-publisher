from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database (supports PostgreSQL or SQLite for dev)
    database_url: str = "sqlite+aiosqlite:///agent_publisher.db"

    # Tencent Cloud
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""

    # Tencent Cloud COS (Object Storage) — optional media backend
    # When configured, uploaded media is stored in COS instead of local disk.
    # Media served via COS CDN URL can be used directly in WeChat article HTML.
    # cos_base_url: custom CDN domain, e.g. "https://cdn.example.com"
    #               leave empty to use default COS URL.
    cos_secret_id: str = ""
    cos_secret_key: str = ""
    cos_bucket: str = ""        # e.g. "my-bucket-1250000000"
    cos_region: str = "ap-beijing"
    cos_base_url: str = ""      # optional CDN domain prefix

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
    # Runtime-added whitelist emails (from invite code activation)
    _runtime_whitelist: set[str] = set()

    # Server
    host: str = "0.0.0.0"
    port: int = 9099
    debug: bool = False

    # Public-facing server host for display (WeChat IP whitelist, guide page, etc.)
    # Can be a domain (e.g. "publisher.example.com") or IP (e.g. "1.2.3.4").
    # If empty, auto-detected from outbound socket.
    server_host: str = ""

    # HTTP proxy for WeChat API calls only (e.g. "http://1.2.3.4:8080")
    # Useful when the server IP is not on WeChat IP whitelist and a proxy
    # server with a whitelisted IP is available.
    # Leave empty to disable. Only affects WeChatService calls.
    wechat_proxy: str = ""

    # WeChat Third-party Platform (扫码授权公众号)
    # 在微信开放平台 https://open.weixin.qq.com 注册第三方平台后获取
    # 配置后用户可通过扫码一键授权公众号，无需手动填写 AppID/AppSecret
    # 详见: docs/wechat-platform-setup.md
    wechat_platform_appid: str = ""         # 第三方平台 AppID
    wechat_platform_secret: str = ""        # 第三方平台 AppSecret
    wechat_platform_token: str = ""         # 消息校验 Token（自定义，需与开放平台一致）
    wechat_platform_aes_key: str = ""       # 消息加解密 Key（自定义，需与开放平台一致）

    # Trending hotspot auto-refresh interval in minutes (0 = disabled).
    # Default: every 60 minutes. Scheduler picks this up at startup.
    trending_refresh_interval: int = 60

    # Membership / payment placeholder contact
    contact_wechat_qr: str = ""
    contact_wechat_id: str = ""
    contact_description: str = "当前支付能力建设中，请联系管理员微信完成开通。"

    # TrendRadar Integration (Phase 1)
    # Enable/disable TrendRadar backend for trending data collection
    # When enabled, Agent Publisher will use TrendRadar's 11-platform aggregation
    # instead of NewsNow API. Feature flag for gradual rollout.
    trendradar_enabled: bool = False

    # Path to TrendRadar data storage (if not using live API)
    # Can be local SQLite path or S3 URL depending on deployment
    trendradar_storage_path: str = ""

    # TrendRadar API/service endpoint (if running as separate service)
    trendradar_service_url: str = ""

    # Which platforms to prioritize from TrendRadar (comma-separated)
    # Default: all 11 platforms (weibo,douyin,xiaohongshu,baidu,zhihu,toutiao,bilibili,v2ex,github,newsnow,rss)
    trendradar_platforms: str = "weibo,douyin,xiaohongshu,baidu,zhihu,toutiao,bilibili,v2ex,github,newsnow,rss"

    # AI analysis integration (Phase 2 - display TrendRadar AI insights in UI)
    trendradar_ai_analysis_enabled: bool = False

    # Material pool unification (Phase 3 - unified sourcing)
    trendradar_unified_pool_enabled: bool = False

    # MCP tool integration (Phase 4 - enrichment during article generation)
    trendradar_mcp_enabled: bool = False

    # Multi-channel publishing (Phase 5 - publish to TrendRadar notification channels)
    trendradar_multi_channel_enabled: bool = False

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
        return (
            email_lower in self.get_email_whitelist()
            or email_lower in self.get_admin_emails()
            or email_lower in self._runtime_whitelist
        )

    def add_to_whitelist(self, email: str) -> None:
        """Add an email to the runtime whitelist (not persisted to .env)."""
        self._runtime_whitelist.add(email.strip().lower())

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
