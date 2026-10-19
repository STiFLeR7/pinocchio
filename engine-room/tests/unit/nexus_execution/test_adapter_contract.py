"""Unit tests for nexus_execution.adapter — the materialized nine-concern contract types."""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_execution.adapter import (
    AdapterConfig,
    ConfiguredRuntime,
    ExecutionControl,
    RuntimeAdapter,
    TeardownReport,
)
from tests.unit.nexus_execution.helpers import FakeAdapter


def test_adapter_config_defaults_are_secret_free() -> None:
    config = AdapterConfig(working_dir="/tmp/work")
    assert config.env_keys == ()
    assert config.secret_refs == ()
    assert config.isolation_profile == "process"
    assert config.limits == {}


def test_adapter_config_carries_secret_references_not_values() -> None:
    config = AdapterConfig(
        working_dir="/w",
        env_keys=("ANTHROPIC_API_KEY",),
        secret_refs=(Reference(target_type="secret", identifier="anthropic_api_key"),),
    )
    # References only — the config never holds a secret value.
    assert config.secret_refs[0].identifier == "anthropic_api_key"
    assert "ANTHROPIC_API_KEY" in config.env_keys


def test_configured_runtime_echo() -> None:
    echo = ConfiguredRuntime(
        runtime_identity="r", isolation_profile="container", working_dir="/w", env_keys=("K",)
    )
    assert echo.runtime_identity == "r"
    assert echo.isolation_profile == "container"


def test_teardown_report_ok_and_failure() -> None:
    assert TeardownReport(ok=True).detail is None
    assert TeardownReport(ok=False, detail="leak").ok is False


def test_execution_control_defaults() -> None:
    control = ExecutionControl()
    assert control.cancelled is False
    assert control.deadline_steps is None


def test_execution_control_cancel_is_idempotent() -> None:
    control = ExecutionControl()
    control.cancel()
    control.cancel()
    assert control.cancelled is True


def test_execution_control_deadline() -> None:
    assert ExecutionControl(deadline_steps=5).deadline_steps == 5


def test_fake_adapter_satisfies_runtime_adapter_protocol() -> None:
    adapter = FakeAdapter(())
    assert isinstance(adapter, RuntimeAdapter)


def test_adapter_configure_is_recorded() -> None:
    adapter = FakeAdapter(())
    echo = adapter.configure(AdapterConfig(working_dir="/w", env_keys=("K",)))
    assert echo.working_dir == "/w"
    assert adapter.configured_with is not None
