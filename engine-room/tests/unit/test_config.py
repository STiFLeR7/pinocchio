"""Unit tests for configuration loading."""

from __future__ import annotations

from nexus.config import NexusSettings


def test_default_execution_timeouts() -> None:
    """Verify that default execution timeout configuration matches specs."""
    settings = NexusSettings()
    assert settings.execution.research_timeout == 900
    assert settings.execution.gemini_timeout == 1800
    assert settings.execution.claude_timeout == 2700
    assert settings.execution.hard_limit == 3600


def test_settings_fixture_loads(test_settings: NexusSettings) -> None:
    """Verify that the test settings fixture loads correctly."""
    assert isinstance(test_settings, NexusSettings)
    assert test_settings.discord.token == "test-token"


def test_database_url_configured(test_settings: NexusSettings) -> None:
    """Verify database URL points to sqlite database."""
    assert "sqlite" in test_settings.database.url
