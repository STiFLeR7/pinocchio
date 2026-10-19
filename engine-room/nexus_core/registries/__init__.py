"""Registry interfaces (ADR-002) — definitions only, no implementations.

Per ADR-002 there are exactly four registries with non-overlapping
responsibilities:

- :class:`CapabilityRegistry` — abstract "what can be done" (no provider state).
- :class:`HarnessRegistry` — concrete integration boundaries; the **sole** owner
  of provider availability and health. A Runtime is a Harness of category Runtime.
- :class:`SkillRegistry` — reusable operational procedures.
- :class:`PolicyRegistry` — governance/operational policies (evaluated only by
  the Policy Engine).

These are ``Protocol`` interfaces so consumers depend on abstractions, not
implementations (dependency inversion). Implementations belong to later phases.
No additional registries may be introduced (ADR-002).
"""

from nexus_core.registries.interfaces import (
    CapabilityRegistry,
    HarnessCategory,
    HarnessDescriptor,
    HarnessRegistry,
    PolicyRegistry,
    SkillRegistry,
)

__all__ = [
    "CapabilityRegistry",
    "HarnessCategory",
    "HarnessDescriptor",
    "HarnessRegistry",
    "PolicyRegistry",
    "SkillRegistry",
]
