"""Sandbox container lifecycle services and orphan cleanups (AP-503)."""

from __future__ import annotations

import asyncio

import structlog

logger = structlog.get_logger("nexus.execution.sandbox.lifecycle")


class SandboxLifecycleService:
    """Manages active sandbox runtimes, cleaning up orphaned Docker containers on reboot."""

    @staticmethod
    async def cleanup_orphaned_sandboxes() -> int:
        """Scan Docker for running containers with names starting with 'nexus_sandbox_' and prune them.

        Returns:
            The count of terminated orphan containers.
        """
        try:
            # 1. List all active sandbox containers
            proc = await asyncio.create_subprocess_exec(
                "docker", "ps", "-a", "--filter", "name=nexus_sandbox_", "--format", "{{.Names}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.debug("docker_ps_failed", error=stderr.decode().strip())
                return 0

            names = [n.strip() for n in stdout.decode().splitlines() if n.strip()]
            cleaned_count = 0

            for name in names:
                if name.startswith("nexus_sandbox_"):
                    logger.warn("terminating_orphaned_container", container_name=name)
                    # Force remove the orphaned sandbox container
                    rm_proc = await asyncio.create_subprocess_exec(
                        "docker", "rm", "-f", name,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await rm_proc.wait()
                    cleaned_count += 1
            return cleaned_count

        except Exception as e:
            # Docker might not be installed or daemon might be offline — fail-safe
            logger.debug("sandbox_orphan_cleanup_skipped", reason=str(e))
            return 0
