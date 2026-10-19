"""``python -m nexus_scheduler`` — the v2 constitutional-platform process entrypoint (RC1).

Boots the full durable constitutional spine (pipeline + approval exchange + operations + scheduler)
over a durable SQLite event log and calls ``Scheduler.tick(now)`` against the real wall clock until
interrupted. Per the Operator Guide (doc §7): "nothing fires on a wall clock inside the platform... an
operator (or a host process's own scheduler) must call ``tick(now)`` periodically." This module *is*
that host process — the single blocker named "no entrypoint launches it" (P17 report, GA Checklist).

It owns no goal-authoring logic: registering a ``SpineRequest``/schedule is a caller concern via the
same public composition-root API this module wires (see :func:`nexus_scheduler.Scheduler.schedule_goal`
and the reference driver scripts under ``scripts/``), so this introduces no new constitutional
capability — only process bootstrap, exactly as ``nexus/__main__.py`` boots v1's ASGI server without
authoring requests itself. The two entrypoints are independent processes: v1 is untouched, there is no
shared startup logic and no import in either direction (cross-stratum isolation, P17 §1).

Lives in ``nexus_scheduler`` (not ``nexus_workflows``) because it only ever needs to import *downstream*
along this package's own already-documented one-way dependency direction (``nexus_scheduler ->
{nexus_workflows.spine, nexus_approval, nexus_operations, ...}``) — nothing points back at it. This
also means it never imports ``nexus_runtime`` (an execution engine, per ``test_guardrails.py`` — the
Scheduler owns timing only); the real wall-clock timestamp source below is a local one-line adapter
over :func:`nexus_scheduler.events.system_now`, mirroring how every other subsystem re-declares its own
``system_now`` rather than importing an earlier layer's.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from nexus_approval import ApprovalExchange, build_approval_exchange
from nexus_infra import InfrastructureContext, LoggingObservability, build_durable_infrastructure
from nexus_operations import OperationsContext, build_operations
from nexus_scheduler.composition import build_scheduler
from nexus_scheduler.events import system_now
from nexus_scheduler.scheduler import Scheduler
from nexus_workflows.spine import SpinePipelineContext, build_constitutional_pipeline

DEFAULT_DB_PATH = "nexus_v2.db"
DEFAULT_TICK_INTERVAL_SECONDS = 5.0
_LOGGER = logging.getLogger("nexus.v2")


class _RealTime:
    """Adapts :func:`nexus_scheduler.events.system_now` to the ``TimestampSource`` protocol shape."""

    def now(self) -> str:
        return system_now()


@dataclass(frozen=True, slots=True)
class PlatformContext:
    """Everything one v2 process needs: the durable spine, its governance seams, and its timing loop."""

    infrastructure: InfrastructureContext
    spine: SpinePipelineContext
    approval: ApprovalExchange
    operations: OperationsContext
    scheduler: Scheduler


def bootstrap(db_path: str) -> PlatformContext:
    """Wire the full constitutional platform over one durable event log.

    Reuses every existing composition root unchanged (``build_durable_infrastructure``,
    ``build_constitutional_pipeline``, ``build_approval_exchange``, ``build_operations``,
    ``build_scheduler``) with production-real seams: a durable file, the real wall clock (never
    ``FixedTimestampSource``), and :class:`~nexus_infra.LoggingObservability` so every subsystem's
    instrumentation reaches a configurable logger instead of going nowhere. Introduces no new wiring
    decision.
    """
    infra = build_durable_infrastructure(db_path, observability=LoggingObservability())
    spine = build_constitutional_pipeline(infra, timestamps=_RealTime())
    approval = build_approval_exchange(spine.coordinator, infra)
    operations = build_operations(spine.coordinator, approval, infra)
    scheduler_ctx = build_scheduler(spine, approval, operations)
    return PlatformContext(
        infrastructure=infra,
        spine=spine,
        approval=approval,
        operations=operations,
        scheduler=scheduler_ctx.scheduler,
    )


def run_service(
    scheduler: Scheduler,
    *,
    tick_interval: float = DEFAULT_TICK_INTERVAL_SECONDS,
    max_ticks: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Call ``scheduler.tick(now)`` against the real wall clock until interrupted; returns tick count.

    ``max_ticks`` bounds the loop (a single ``--once`` invocation, or a deterministic test); left
    ``None`` for a long-running service, stopped by SIGINT/SIGTERM (``KeyboardInterrupt``).
    """
    now = system_now
    ticks = 0
    while True:
        outcomes = scheduler.tick(now())
        if outcomes:
            _LOGGER.info("tick dispatched %d occurrence(s)", len(outcomes))
        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            break
        sleep(tick_interval)
    return ticks


def main(argv: list[str] | None = None) -> None:
    """Boot the v2 constitutional platform and run its scheduler loop until interrupted."""
    parser = argparse.ArgumentParser(
        prog="nexus-v2", description="Nexus v2 constitutional platform"
    )
    parser.add_argument("--db", default=os.environ.get("NEXUS_V2_DB", DEFAULT_DB_PATH))
    parser.add_argument("--tick-interval", type=float, default=DEFAULT_TICK_INTERVAL_SECONDS)
    parser.add_argument("--once", action="store_true", help="run a single tick then exit")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    _LOGGER.info("starting_nexus_v2 db=%s tick_interval=%s", args.db, args.tick_interval)

    platform = bootstrap(args.db)
    try:
        run_service(
            platform.scheduler,
            tick_interval=args.tick_interval,
            max_ticks=1 if args.once else None,
        )
    except KeyboardInterrupt:
        _LOGGER.info("nexus_v2_shutdown_requested")
        sys.exit(0)


if __name__ == "__main__":
    main()
