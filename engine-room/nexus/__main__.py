"""Nexus entry point.

Configures structured logging and launches the FastAPI application
via uvicorn on the configured host and port.
"""

from __future__ import annotations

import sys

import structlog
import uvicorn

from nexus.config import get_settings
from nexus.logging_config import setup_logging


def main() -> None:
    """Bootstrap Nexus: configure logging, then start the ASGI server.

    ``python -m nexus onboard`` runs the operator onboarding flow (safe, read-only) instead of
    starting the server.
    """
    if "onboard" in sys.argv[1:]:
        from nexus.onboarding import main as onboarding_main

        onboarding_main()
        return

    settings = get_settings()
    setup_logging(
        level=settings.logging.level,
        log_format=settings.logging.format,
    )
    logger = structlog.get_logger("nexus.main")
    logger.info(
        "starting_nexus",
        version=settings.version,
        host="0.0.0.0",
        port=8000,
    )

    try:
        uvicorn.run(
            "nexus.api:app",
            host="0.0.0.0",
            port=8000,
            log_level=settings.logging.level.lower(),
            reload=False,
        )
    except KeyboardInterrupt:
        logger.info("nexus_shutdown_requested")
        sys.exit(0)


if __name__ == "__main__":
    main()
