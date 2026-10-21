"""Artifact collection routines from container filesystem workspaces."""

from __future__ import annotations

import asyncio

import structlog

logger = structlog.get_logger("nexus.execution.sandbox.collector")


class SandboxArtifactCollector:
    """Retrieves execution results and files generated inside isolated container runtimes."""

    @staticmethod
    async def collect_file(sandbox_id: str, container_path: str, host_path: str) -> bool:
        """Copy a file out of a Docker sandbox container to the host filesystem.

        Args:
            sandbox_id: The unique identifier of the sandbox container.
            container_path: Absolute file path inside the sandbox container.
            host_path: Destination path on the host filesystem.

        Returns:
            True if copy succeeded, False otherwise.
        """
        container_name = f"nexus_sandbox_{sandbox_id}"
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "cp", f"{container_name}:{container_path}", host_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            if proc.returncode == 0:
                logger.info("artifact_collected_successfully", sandbox_id=sandbox_id, path=host_path)
                return True
            else:
                logger.warn("artifact_collection_failed", error=proc.returncode)
                return False
        except Exception as e:
            logger.warn("artifact_collection_error", error=str(e))
            return False
