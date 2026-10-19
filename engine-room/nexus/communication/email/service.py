"""Service layer for generic SMTP email delivery using aiosmtplib (AP-307)."""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiosmtplib
import structlog

from nexus.config import get_settings

logger = structlog.get_logger("nexus.communication.email.service")


class EmailService:
    """Generic SMTP client adapter supporting multi-provider configuration (AP-307)."""

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings or get_settings()

    async def send_briefing_email(self, subject: str, text_content: str, html_content: str) -> None:
        """Construct and send an email containing text and HTML formats via SMTP."""
        email_cfg = self.settings.email
        if not email_cfg.smtp_host:
            logger.warning("email_smtp_host_not_configured_skipping_delivery")
            return

        # Prepare message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = email_cfg.from_address
        msg["To"] = email_cfg.to_address

        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        msg.attach(part1)
        msg.attach(part2)

        # SMTP Connection settings
        connect_kwargs: dict[str, Any] = {
            "hostname": email_cfg.smtp_host,
            "port": email_cfg.smtp_port,
        }

        # Determine TLS / SSL configurations
        use_tls = getattr(email_cfg, "use_tls", True)

        # Connect and send
        try:
            logger.info(
                "connecting_to_smtp_server",
                host=email_cfg.smtp_host,
                port=email_cfg.smtp_port,
            )

            # Connect via SMTP
            # If use_tls is True and port is 465, use direct SMTP_SSL, otherwise use STARTTLS on connect
            if use_tls and email_cfg.smtp_port == 465:
                smtp_client = aiosmtplib.SMTP(use_tls=True, **connect_kwargs)
            else:
                # start_tls=False prevents aiosmtplib from auto-negotiating STARTTLS during
                # connect(); the explicit starttls() below then performs the single upgrade
                # (fixes "Connection already using TLS" double-STARTTLS on :587).
                smtp_client = aiosmtplib.SMTP(use_tls=False, start_tls=False, **connect_kwargs)

            await smtp_client.connect()

            # Upgrade to TLS if port is not 465 and use_tls is enabled
            if use_tls and email_cfg.smtp_port != 465:
                await smtp_client.starttls()

            # Authenticate if credentials are provided
            if email_cfg.username and email_cfg.password:
                await smtp_client.login(email_cfg.username, email_cfg.password)

            await smtp_client.send_message(msg)
            await smtp_client.quit()

            logger.info("email_sent_successfully", subject=subject, recipient=email_cfg.to_address)
        except Exception as e:
            logger.error("email_delivery_failed", host=email_cfg.smtp_host, error=str(e))
            raise
