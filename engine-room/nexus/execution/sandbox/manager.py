"""Central Sandbox Manager coordinating providers and audits (AP-503)."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.core.exceptions import ConfigurationError, SandboxResolutionError
from nexus.execution.sandbox.audit import SandboxAuditIntegration
from nexus.execution.sandbox.provider import (
    RECOGNIZED_PROVIDERS,
    LocalSandboxProvider,
    SandboxPolicy,
    SandboxProcess,
    SandboxProvider,
)

logger = structlog.get_logger("nexus.execution.sandbox.manager")


class SandboxManager:
    """Orchestrates runtime execution sandboxing, applying resource limits and logging audits."""

    def __init__(self, db_session: AsyncSession, settings: Any = None):
        """Initialize the SandboxManager with DB session and configurations."""
        self.session = db_session
        self.settings = settings
        self.audit = SandboxAuditIntegration(db_session)
        self.provider = self._resolve_provider()

    def _resolve_provider(self) -> SandboxProvider:
        """Resolve the active SandboxProvider, fail-closed (S-2 / A-006 R-01, R-02).

        Default-secure resolution: a real configuration must explicitly enable sandboxing and name a
        recognized provider. Isolation that is disabled, or an unrecognized provider name, raises
        ``SandboxResolutionError`` rather than silently executing on the host.

        The non-production construction path (``settings`` is not a ``NexusSettings`` — e.g. ``None``
        or a test double) is intentionally retained as ``LocalSandboxProvider`` to preserve
        runtime-adapter/e2e construction contracts; production always supplies ``NexusSettings``.
        """
        from nexus.config import NexusSettings
        if not isinstance(self.settings, NexusSettings) or not self.settings.sandbox:
            return LocalSandboxProvider()

        cfg = self.settings.sandbox
        if not cfg.enabled:
            raise SandboxResolutionError(
                "Sandbox is disabled (sandbox.enabled is False). Refusing to execute on the host "
                "implicitly (fail-closed). Set sandbox.enabled=true and choose a provider "
                "(docker for isolation, or local to deliberately run on the host)."
            )

        provider_name = cfg.provider.lower()
        provider_cls = RECOGNIZED_PROVIDERS.get(provider_name)
        if provider_cls is None:
            raise SandboxResolutionError(
                f"Unknown sandbox provider '{cfg.provider}'. Refusing to fall back to host "
                f"execution (fail-closed). Recognized providers: {sorted(RECOGNIZED_PROVIDERS)}."
            )
        return provider_cls()

    async def execute(
        self,
        command: str,
        cwd: str = ".",
        timeout: int = 300,
        correlation_id: uuid.UUID | None = None,
    ) -> SandboxProcess:
        """Provision a sandbox, log creation audits, start the process, and return its handle.

        Args:
            command: The command execution string to launch.
            cwd: The workspace working directory path on the host.
            timeout: Maximum execution timeout in seconds.
            correlation_id: The trace ID (execution_id) correlating system events.

        Returns:
            A SandboxProcess wrapper handle.
        """
        sandbox_id = str(uuid.uuid4())

        # Resolve containment policies
        cpu_limit = 1.0
        memory_limit = "512m"
        network_policy = "none"
        filesystem_policy = "restricted"
        image = "python:3.12-slim"

        from nexus.config import NexusSettings
        if isinstance(self.settings, NexusSettings) and self.settings.sandbox:
            cfg = self.settings.sandbox
            cpu_limit = cfg.cpu_limit
            memory_limit = cfg.memory_limit
            network_policy = cfg.network_policy
            filesystem_policy = cfg.filesystem_policy
            image = cfg.image

        policy = SandboxPolicy(
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
            timeout=timeout,
            network_policy=network_policy,
            filesystem_policy=filesystem_policy,
            image=image,
        )

        # 1. Audit: SandboxCreated
        await self.audit.audit_event(
            event_type="sandbox.created",
            sandbox_id=sandbox_id,
            data={
                "command": command,
                "cwd": cwd,
                "policy": policy.model_dump(),
                # R-03: declare honestly whether the resolved provider enforces the policy, rather
                # than recording a policy the host (local) provider silently ignores.
                "policy_enforced": self.provider.enforces_policy,
            },
            correlation_id=correlation_id,
        )

        # 2. Audit: SandboxStarted
        await self.audit.audit_event(
            event_type="sandbox.started",
            sandbox_id=sandbox_id,
            correlation_id=correlation_id,
        )

        try:
            process = await self.provider.spawn(command, policy, cwd, sandbox_id)
            original_communicate = process.communicate

            # Intercept communicate to record audit terminations or failures
            async def wrapped_communicate() -> tuple[bytes, bytes]:
                try:
                    stdout, stderr = await original_communicate()
                    err_str = stderr.decode("utf-8", errors="replace")

                    if process.returncode != 0:
                        # Differentiate timeout vs failure
                        if "timeout" in err_str.lower() or process.returncode == -1:
                            await self.audit.audit_event(
                                event_type="sandbox.timeout",
                                sandbox_id=sandbox_id,
                                data={
                                    "exit_code": process.returncode,
                                    "stderr": err_str[:500],
                                },
                                correlation_id=correlation_id,
                            )
                        else:
                            await self.audit.audit_event(
                                event_type="sandbox.failure",
                                sandbox_id=sandbox_id,
                                data={
                                    "exit_code": process.returncode,
                                    "stderr": err_str[:500],
                                },
                                correlation_id=correlation_id,
                            )
                    else:
                        # Successful execution termination
                        await self.audit.audit_event(
                            event_type="sandbox.terminated",
                            sandbox_id=sandbox_id,
                            data={"exit_code": 0},
                            correlation_id=correlation_id,
                        )
                    return stdout, stderr
                except Exception as ex:
                    await self.audit.audit_event(
                        event_type="sandbox.failure",
                        sandbox_id=sandbox_id,
                        data={"error": str(ex)},
                        correlation_id=correlation_id,
                    )
                    raise ex

            process.communicate = wrapped_communicate  # type: ignore[method-assign]
            return process

        except Exception as spawn_err:
            await self.audit.audit_event(
                event_type="sandbox.failure",
                sandbox_id=sandbox_id,
                data={"error": f"Failed to spawn: {spawn_err!s}"},
                correlation_id=correlation_id,
            )
            raise spawn_err


async def validate_sandbox_startup(settings: Any) -> None:
    """Startup gate for execution sandboxing (S-3 / A-006 R-06, R-07).

    Mirrors the A-001 owner gate: validates the sandbox configuration and the availability of the
    configured provider at boot, so unsafe or unusable sandbox states fail fast instead of being
    discovered at first command execution.

    Behavior:
      * Disabled / unconfigured sandbox: allowed (warned) — execution still fails closed at runtime
        (S-2), so this is a safe, visible state, not a startup-fatal one.
      * Unknown provider: aborts startup (``ConfigurationError``) — coherence.
      * Policy-enforcing provider (e.g. docker) unavailable: aborts startup
        (``ConfigurationError``) — eliminates delayed runtime discovery (R-06).
      * Non-enforcing provider (local/host): allowed but loudly warned — deliberate, declared
        host execution (R-03). Each actual host execution is additionally recorded in the immutable
        audit ledger with ``policy_enforced=false``.

    Raises:
        ConfigurationError: when the sandbox configuration is incoherent or the configured
            policy-enforcing provider is unavailable.
    """
    from nexus.config import NexusSettings

    cfg = settings.sandbox if isinstance(settings, NexusSettings) else None
    if cfg is None or not cfg.enabled:
        logger.warning(
            "sandbox_disabled_at_startup",
            detail=(
                "Sandbox is disabled; governed command execution will fail closed until a provider "
                "is configured (sandbox.enabled=true)."
            ),
        )
        return

    provider_name = cfg.provider.lower()
    provider_cls = RECOGNIZED_PROVIDERS.get(provider_name)
    if provider_cls is None:
        raise ConfigurationError(
            f"Startup aborted: unknown sandbox provider '{cfg.provider}'. Recognized providers: "
            f"{sorted(RECOGNIZED_PROVIDERS)}."
        )

    provider = provider_cls()
    try:
        await provider.ensure_available()
    except SandboxResolutionError as exc:
        raise ConfigurationError(
            f"Startup aborted: sandbox provider '{provider_name}' is unavailable: {exc}"
        ) from exc

    if not provider.enforces_policy:
        logger.warning(
            "sandbox_host_unsafe_at_startup",
            provider=provider_name,
            detail=(
                "Selected sandbox provider does not enforce isolation policy; commands run without "
                "containment. Deliberate, audited host-execution choice."
            ),
        )
    else:
        logger.info("sandbox_startup_validated", provider=provider_name)
