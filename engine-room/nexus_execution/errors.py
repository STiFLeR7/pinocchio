"""Execution error model — adapter/engine failures mapped onto the doc-11 taxonomy.

The Execution Engine never invents an error class: every failure it surfaces is one of the
provider-independent classes doc 11 already defines. The adapter reports a provider fault;
the engine classifies the *surfaced* outcome (doc 11 §5, doc 23 §6) and records it in the
``runtime.failed`` payload (doc 15) as ``{error_class, owner, detail}``. There is no new
error class here — only concrete Python types carrying the canonical ``error_class`` /
``owner`` strings.
"""

from __future__ import annotations


class ExecutionError(Exception):
    """Base for every engine-surfaced fault. Subclasses fix the doc-11 class + owner."""

    error_class: str = "execution-failure"
    owner: str = "runtime"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ExecutionStartupError(ExecutionError):
    """The runtime could not be brought up for the Work Package (doc 11, concern C)."""

    error_class = "execution-startup-failure"
    owner = "runtime"


class TransportError(ExecutionError):
    """A wire/transport fault reaching the runtime (doc 11 §2.4, doc 23 §6)."""

    error_class = "transport-failure"
    owner = "transport"


class ProviderError(ExecutionError):
    """The provider/runtime itself errored or crashed (doc 11)."""

    error_class = "provider-failure"
    owner = "provider"


class RuntimeTimeoutError(ExecutionError):
    """A timeout bound elapsed before the runtime finished (doc 10, doc 11)."""

    error_class = "timeout"
    owner = "runtime"


class UserCancellationError(ExecutionError):
    """Execution stopped by an explicit cancellation (doc 09, doc 11)."""

    error_class = "user-cancellation"
    owner = "user"


class InfrastructureError(ExecutionError):
    """The substrate (event store, repositories) failed the engine (doc 11)."""

    error_class = "infrastructure-failure"
    owner = "infrastructure"


class TeardownError(ExecutionError):
    """Adapter cleanup failed; surfaced, never hidden — the session still reaches Destroyed."""

    error_class = "teardown-failure"
    owner = "runtime"
