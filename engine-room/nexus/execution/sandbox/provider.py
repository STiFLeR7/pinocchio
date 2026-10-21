"""Sandbox execution provider implementations (AP-503)."""

from __future__ import annotations

import abc
import asyncio
import os
from typing import Any

from pydantic import BaseModel

from nexus.core.exceptions import SandboxUnavailableError


class SandboxPolicy(BaseModel):
    """Execution containment policy rules."""

    cpu_limit: float = 1.0
    memory_limit: str = "512m"
    timeout: int = 300
    network_policy: str = "none"
    filesystem_policy: str = "restricted"
    image: str = "python:3.12-slim"


class SandboxProcess:
    """Standardized handle to execute, control, and communicate with a sandbox."""

    def __init__(self, process_id: str, provider: SandboxProvider):
        self.pid = process_id  # UUID or container name/id
        self.provider = provider
        self.returncode: int | None = None
        self._stdout: bytes = b""
        self._stderr: bytes = b""
        self._completed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        """Await process completion and return stdout/stderr logs."""
        if not self._completed:
            stdout, stderr, exit_code = await self.provider.wait_and_capture(self.pid)
            self.returncode = exit_code
            self._stdout = stdout
            self._stderr = stderr
            self._completed = True
        return self._stdout, self._stderr

    def terminate(self) -> None:
        """Abort execution by killing the running container/process."""
        # Non-blocking wrapper for compatibility with sync calls in adapters
        self._terminate_task = asyncio.create_task(self.provider.terminate(self.pid))

    async def wait(self) -> int:
        """Wait for completion and return exit code."""
        if not self._completed:
            await self.communicate()
        return self.returncode or 0


class SandboxProvider(abc.ABC):
    """Abstract base class for all sandbox containers."""

    #: Whether this provider actually enforces the SandboxPolicy (cpu/memory/network/filesystem).
    #: Used to audit honestly and to drive startup validation (S-3 / A-006 R-03). Defaults to
    #: False so a provider must opt in to claiming enforcement.
    enforces_policy: bool = False

    async def ensure_available(self) -> None:
        """Verify the provider can run before any execution (S-3 / A-006 R-06).

        Default: available (no external dependency). Providers with external runtimes override this
        to fail closed when their runtime is unreachable.
        """
        return None

    @abc.abstractmethod
    async def spawn(
        self,
        command: str,
        policy: SandboxPolicy,
        cwd: str,
        sandbox_id: str,
    ) -> SandboxProcess:
        """Create and start the isolated execution context."""
        pass

    @abc.abstractmethod
    async def wait_and_capture(self, process_id: str) -> tuple[bytes, bytes, int]:
        """Await execution completion and capture outputs."""
        pass

    @abc.abstractmethod
    async def terminate(self, process_id: str) -> None:
        """Forcefully kill the isolated execution process."""
        pass


class LocalSandboxProvider(SandboxProvider):
    """Fallback provider running commands directly on the host OS (sandbox-disabled fallback)."""

    def __init__(self) -> None:
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def spawn(
        self,
        command: str,
        policy: SandboxPolicy,
        cwd: str,
        sandbox_id: str,
    ) -> SandboxProcess:
        # Spawn direct host process
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        self._processes[sandbox_id] = proc
        return SandboxProcess(sandbox_id, self)

    async def wait_and_capture(self, process_id: str) -> tuple[bytes, bytes, int]:
        proc = self._processes.get(process_id)
        if not proc:
            return b"", b"Process not found", -1
        try:
            stdout, stderr = await proc.communicate()
            return stdout, stderr, proc.returncode or 0
        finally:
            self._processes.pop(process_id, None)

    async def terminate(self, process_id: str) -> None:
        proc = self._processes.get(process_id)
        if proc:
            try:
                proc.terminate()
                await proc.wait()
            except Exception:
                pass
            finally:
                self._processes.pop(process_id, None)


class DockerSandboxProvider(SandboxProvider):
    """Production provider encapsulating runs inside Docker containers."""

    #: Docker enforces the SandboxPolicy via --cpus/--memory/--network/-v (see ``spawn``).
    enforces_policy: bool = True

    def __init__(self) -> None:
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def ensure_available(self) -> None:
        """Fail closed unless the Docker runtime is reachable (``docker version`` exits 0)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            returncode = await proc.wait()
        except FileNotFoundError as exc:
            raise SandboxUnavailableError(
                "Docker CLI not found on PATH. Refusing to start with provider='docker' "
                "(fail-closed). Install Docker or choose another sandbox provider."
            ) from exc
        if returncode != 0:
            raise SandboxUnavailableError(
                f"Docker runtime is not reachable ('docker version' exited {returncode}). "
                "Refusing to start with provider='docker' (fail-closed)."
            )

    async def spawn(
        self,
        command: str,
        policy: SandboxPolicy,
        cwd: str,
        sandbox_id: str,
    ) -> SandboxProcess:
        container_name = f"nexus_sandbox_{sandbox_id}"

        args = ["run", "--name", container_name, "--rm", "-i"]

        # 1. Resource Limits (CPU, Memory)
        if policy.cpu_limit:
            args.extend(["--cpus", str(policy.cpu_limit)])
        if policy.memory_limit:
            args.extend(["--memory", policy.memory_limit])

        # 2. Network Isolation
        if policy.network_policy:
            args.extend(["--network", policy.network_policy])

        # 3. Filesystem Isolation (Restricted workspace volume mounting)
        host_path = os.path.abspath(cwd).replace("\\", "/")
        mount_option = f"{host_path}:/workspace"
        if policy.filesystem_policy == "readonly":
            mount_option += ":ro"
        args.extend(["-v", mount_option, "-w", "/workspace"])

        # 4. Image definition
        args.append(policy.image)

        # 5. Shell Command execution
        args.extend(["sh", "-c", command])

        # Spawn via Docker CLI
        proc = await asyncio.create_subprocess_exec(
            "docker",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._processes[sandbox_id] = proc
        return SandboxProcess(sandbox_id, self)

    async def wait_and_capture(self, process_id: str) -> tuple[bytes, bytes, int]:
        proc = self._processes.get(process_id)
        if not proc:
            return b"", b"Sandbox container not found", -1
        try:
            stdout, stderr = await proc.communicate()
            return stdout, stderr, proc.returncode or 0
        finally:
            self._processes.pop(process_id, None)

    async def terminate(self, process_id: str) -> None:
        container_name = f"nexus_sandbox_{process_id}"
        try:
            kill_proc = await asyncio.create_subprocess_exec(
                "docker", "kill", container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await kill_proc.wait()
        except Exception:
            pass

        proc = self._processes.get(process_id)
        if proc:
            try:
                proc.terminate()
                await proc.wait()
            except Exception:
                pass
            finally:
                self._processes.pop(process_id, None)


class MockSandboxProvider(SandboxProvider):
    """Mock sandbox provider simulating isolation behaviors for lightweight unit testing."""

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}

    async def spawn(
        self,
        command: str,
        policy: SandboxPolicy,
        cwd: str,
        sandbox_id: str,
    ) -> SandboxProcess:
        self._runs[sandbox_id] = {
            "command": command,
            "policy": policy,
            "cwd": cwd,
            "terminated": False,
        }
        return SandboxProcess(sandbox_id, self)

    async def wait_and_capture(self, process_id: str) -> tuple[bytes, bytes, int]:
        run = self._runs.get(process_id)
        if not run:
            return b"", b"Mock sandbox run not found", -1

        cmd = run["command"]

        # Simulating behaviors based on keywords in commands
        if "timeout" in cmd.lower():
            # Simulate a timeout limit hit
            await asyncio.sleep(0.1)
            return b"", b"Timeout: Process exceeded timeout limit.", -1
        elif "crash" in cmd.lower() or "fail" in cmd.lower():
            return b"Initializing...\n", b"Segmentation fault (mock container crash)", 139
        else:
            return f"Mock sandbox run success: {cmd}".encode(), b"", 0

    async def terminate(self, process_id: str) -> None:
        run = self._runs.get(process_id)
        if run:
            run["terminated"] = True


#: The recognized sandbox providers. The single source of truth for both resolution
#: (SandboxManager._resolve_provider) and startup validation (validate_sandbox_startup). Any
#: provider name not in this mapping is rejected fail-closed (S-2/S-3).
RECOGNIZED_PROVIDERS: dict[str, type[SandboxProvider]] = {
    "docker": DockerSandboxProvider,
    "mock": MockSandboxProvider,
    "local": LocalSandboxProvider,
}
