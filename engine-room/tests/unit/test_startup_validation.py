"""A-001 startup-gate tests: fail-closed on missing owner configuration (Nexus v1.0.1).

The application must refuse to start when no Discord owner IDs are configured, because that would
leave approval authorization disabled (fail-open). No degraded/warning/fallback mode is permitted.
"""

from __future__ import annotations

import pytest

from nexus.api import _validate_startup_configuration
from nexus.config import DiscordConfig, NexusSettings
from nexus.core.exceptions import ConfigurationError


def test_startup_fails_with_empty_owner_ids() -> None:
    """Empty owner_ids must abort startup with a ConfigurationError."""
    settings = NexusSettings(discord=DiscordConfig(owner_ids=[]))
    with pytest.raises(ConfigurationError) as exc_info:
        _validate_startup_configuration(settings)
    msg = str(exc_info.value).lower()
    assert "owner" in msg


def test_startup_succeeds_with_owner_ids() -> None:
    """A populated owner_ids list must pass the startup gate without raising."""
    settings = NexusSettings(discord=DiscordConfig(owner_ids=[111222333]))
    # Must not raise.
    _validate_startup_configuration(settings)
