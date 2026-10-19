"""Default legacy governance policies and configuration fallbacks."""

from __future__ import annotations

# Platform Allowed Runtimes
# "hermes" retained as the deprecated codename alias for "nexus" (back-compat).
ALLOWED_RUNTIMES = ["gemini", "claude", "nexus", "hermes"]

# Global Command Blacklist Patterns
GLOBAL_COMMAND_BLACKLIST = ["rm -rf /", "sudo ", "mv /etc", ":(){ :|:& };:"]

# Concurrency Gates Defaults
DEFAULT_CONCURRENCY_LIMIT = 3
CONCURRENCY_RETRY_COUNT = 5
CONCURRENCY_RETRY_TIMEOUT = 5.0

# General Policy Constraints
REQUIRED_RUNTIME_POLICY = "approved"
