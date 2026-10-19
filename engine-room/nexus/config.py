"""Nexus configuration management.

Loads configuration from environment variables, ``.env`` files, and
``config/settings.yaml`` using Pydantic Settings.  A cached
``get_settings()`` accessor ensures the settings object is built once.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Nested configuration models
# ---------------------------------------------------------------------------


class DiscordChannels(BaseModel):
    """Channel mapping for Discord bot routing."""

    inbox: str = "nexus-commands"
    tasks: str = "nexus-timeline"
    approvals: str = "nexus-approvals"
    execution_log: str = Field("nexus-logs", alias="execution-log")
    research: str = "nexus-research"
    summaries: str = "nexus-reports"
    alerts: str = "nexus-alerts"
    # Dex v2 operator-facing channel taxonomy.
    general: str = "general"  # free-form chat — Dex replies without an @mention here
    console: str = "console"  # Dex status/action cards (Status / Task Initialized / Complete)
    system_logs: str = Field("system-logs", alias="system-logs")  # whole-repo system logs
    timeline: str = "timeline"  # time management (IST)
    priority_feed: str = Field("priority-feed", alias="priority-feed")  # @owner priority briefs
    reminders: str = "reminders"  # reminders & TODOs

    model_config = ConfigDict(populate_by_name=True)


class DiscordConfig(BaseModel):
    """Discord bot and channel configuration."""

    token: str = ""
    guild_id: int = 0
    owner_ids: list[int] = Field(default_factory=list)
    channels: DiscordChannels = Field(default_factory=DiscordChannels)


class EmailConfig(BaseModel):
    """Email / SMTP configuration."""

    provider: str = "smtp"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    from_address: str = ""
    to_address: str = ""
    use_tls: bool = True


class OpenRouterConfig(BaseModel):
    """OpenRouter LLM gateway configuration."""

    api_key: str = ""
    # Free OpenRouter models (no credit cost) — operational default for unattended bring-up.
    # Primary chosen for reliable JSON tool-call adherence; fallbacks per operator guidance.
    primary_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    fallback_models: list[str] = Field(
        default_factory=lambda: [
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ]
    )
    base_url: str = "https://openrouter.ai/api/v1"


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    url: str = "sqlite+aiosqlite:///./data/nexus.db"
    echo: bool = False


class ExecutionConfig(BaseModel):
    """Timeout thresholds for execution runners (in seconds)."""

    research_timeout: int = 900
    gemini_timeout: int = 1800
    claude_timeout: int = 2700
    hard_limit: int = 3600
    concurrency_retry_count: int = 5
    concurrency_retry_timeout: float = 5.0
    # Nexus agent step budget — operator-tunable; default preserves prior hardcoded value (H-4).
    agent_max_steps: int = 5


class LoggingConfig(BaseModel):
    """Structured logging configuration."""

    level: str = "INFO"
    format: str = "json"


class SchedulingConfig(BaseModel):
    """Scheduler job toggles and cadences (AP-103, additive — no behavior unless enabled)."""

    enabled: bool = True
    timezone: str = "Asia/Kolkata"

    # J1 — Research Collection (every 2h); requires feeds to run, else skipped.
    research_enabled: bool = True
    research_interval_hours: int = 2
    research_feeds: dict[str, str] = Field(default_factory=dict)

    # Proactive Priority Feed — after each research run, push newly-discovered high-importance
    # findings to the PRIORITY_FEED channel (mentions the owner). Discord-agnostic; routes via
    # the channel harness. No effect unless findings clear ``priority_feed_min_score``.
    priority_feed_enabled: bool = True
    priority_feed_min_score: int = 4  # importance_score >= this is "priority" (1-5 scale)
    priority_feed_max_items: int = 5  # cap items per digest; remainder summarized as "+N more"

    # J2 — Daily Briefing (cron, 08:00 in `timezone`)
    briefing_enabled: bool = True
    briefing_hour: int = 8
    briefing_minute: int = 0

    # J3 — Approval Expiration Sweep (every 15m)
    approval_sweep_enabled: bool = True
    approval_sweep_interval_minutes: int = 15

    # J4 — Metrics Aggregation & Retention (every 5m)
    metrics_aggregation_enabled: bool = True
    metrics_aggregation_interval_minutes: int = 5

    # J5 — Outbox Health Monitoring (read-only; every 10m)
    outbox_health_enabled: bool = True
    outbox_health_interval_minutes: int = 10
    outbox_backlog_threshold: int = 100

    # J6 — Checkpoint Health Monitoring (read-only; every 30m)
    checkpoint_health_enabled: bool = True
    checkpoint_health_interval_minutes: int = 30
    checkpoint_stale_minutes: int = 60


class SandboxConfig(BaseModel):
    """Configuration for execution runtime sandbox containment (AP-503)."""

    enabled: bool = False
    provider: str = "local"  # 'local', 'docker', 'mock'
    image: str = "python:3.12-slim"
    cpu_limit: float = 1.0
    memory_limit: str = "512m"
    network_policy: str = "none"
    filesystem_policy: str = "restricted"


# ---------------------------------------------------------------------------
# Root settings
# ---------------------------------------------------------------------------


def _load_yaml_settings(yaml_path: Path) -> dict[str, Any]:
    """Load settings from a YAML file if it exists."""
    if yaml_path.exists():
        with open(yaml_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
            if isinstance(data, dict):
                return data
    return {}


class NexusSettings(BaseSettings):
    """Top-level Nexus application settings.

    Sources (highest to lowest priority):
      1. Environment variables / ``.env``
      2. ``config/settings.yaml``
      3. Field defaults
    """

    model_config = SettingsConfigDict(
        env_prefix="NEXUS_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Metadata
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    # Subsystem configs
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    openrouter: OpenRouterConfig = Field(default_factory=OpenRouterConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    scheduling: SchedulingConfig = Field(default_factory=SchedulingConfig)

    @classmethod
    def from_yaml_and_env(cls, yaml_path: Path | None = None) -> NexusSettings:
        """Construct settings merging YAML defaults with env overrides."""
        path = yaml_path or Path("config/settings.yaml")
        yaml_data = _load_yaml_settings(path)

        import os

        from dotenv import load_dotenv

        load_dotenv()

        # Map environment overrides directly for convenience in local development
        if "discord" not in yaml_data:
            yaml_data["discord"] = {}

        if os.getenv("DISCORD_BOT_TOKEN"):
            yaml_data["discord"]["token"] = os.getenv("DISCORD_BOT_TOKEN")
        import contextlib

        if os.getenv("DISCORD_GUILD_ID"):
            with contextlib.suppress(ValueError):
                yaml_data["discord"]["guild_id"] = int(os.getenv("DISCORD_GUILD_ID", "0"))

        # Load owner IDs if specified as comma-separated or JSON list.
        # ``DISCORD_OWNER_ID`` (singular) is accepted as an operator-friendly alias (config
        # alignment — the deployed .env uses this name).
        owners_env = (
            os.getenv("DISCORD_OWNERS")
            or os.getenv("NEXUS_DISCORD__OWNER_IDS")
            or os.getenv("DISCORD_OWNER_ID")
        )
        if owners_env:
            with contextlib.suppress(ValueError):
                yaml_data["discord"]["owner_ids"] = [int(x.strip()) for x in owners_env.split(",")]

        if "openrouter" not in yaml_data:
            yaml_data["openrouter"] = {}

        if os.getenv("OPENROUTER_API_KEY"):
            yaml_data["openrouter"]["api_key"] = os.getenv("OPENROUTER_API_KEY")

        # Email (SMTP) alignment: read the deployed NOTIFY_* keys into the email config so the
        # existing SMTP EmailService delivers without a parallel credential store. Additive — env
        # values win only when present; .env remains the single source of truth.
        if "email" not in yaml_data:
            yaml_data["email"] = {}
        if os.getenv("NOTIFY_SMTP_SERVER"):
            yaml_data["email"]["smtp_host"] = os.getenv("NOTIFY_SMTP_SERVER")
        if os.getenv("NOTIFY_SMTP_PORT"):
            with contextlib.suppress(ValueError):
                yaml_data["email"]["smtp_port"] = int(os.getenv("NOTIFY_SMTP_PORT", "587"))
        if os.getenv("NOTIFY_SMTP_PASSWORD"):
            yaml_data["email"]["password"] = os.getenv("NOTIFY_SMTP_PASSWORD")
        if os.getenv("NOTIFY_EMAIL_FROM"):
            _from = os.getenv("NOTIFY_EMAIL_FROM")
            yaml_data["email"]["from_address"] = _from
            # Most SMTP providers (e.g. Gmail) authenticate with the sender address as username.
            yaml_data["email"].setdefault("username", _from)
        # Recipient for operational digests/notifications: an explicit NOTIFY_EMAIL_TO wins;
        # otherwise default to the sender address (operator self-delivery) so emails always have a
        # valid RCPT TO. Without this, briefing email fails with SMTP 555 (empty recipient).
        _to = os.getenv("NOTIFY_EMAIL_TO") or os.getenv("NOTIFY_EMAIL_FROM")
        if _to and not yaml_data["email"].get("to_address"):
            yaml_data["email"]["to_address"] = _to

        return cls(**yaml_data)


@lru_cache(maxsize=1)
def get_settings() -> NexusSettings:
    """Return the cached application settings singleton."""
    return NexusSettings.from_yaml_and_env()
