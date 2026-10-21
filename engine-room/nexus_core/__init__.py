"""Nexus v2 — Foundation layer (Phase 1).

Platform primitives only: domain objects, contract validation, registry
interfaces, event primitives, state primitives, and persistence abstractions.

This package contains **no** AI, orchestration, planning, execution, persistence
implementation, scheduling, or API logic. Those belong to later phases. If every
higher-level subsystem were deleted, this foundation must remain correct.

Architecture is frozen (see ``docs/v2/``, ``adr/``, ``contracts/``). This package
implements the frozen contracts exactly; it never redefines them.
"""

__all__ = ["__version__"]

__version__ = "2.5.0"
