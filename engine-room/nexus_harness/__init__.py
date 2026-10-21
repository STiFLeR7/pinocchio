"""``nexus_harness`` — Phase 6 Harness Layer for Nexus v2.

The Harness *compiles*; it never executes. Given the Harness Requests an
Orchestration cycle produced, it validates them and resolves their Skills,
Capabilities, Policies, Context, and Artifacts into immutable, runtime-ready
**Execution Packages** and descriptive **Execution Manifests** — the final
preparation stage before runtime selection and execution::

    … → Orchestration → Harness → Execution Package → Runtime Manager → Execution Engine

It never invokes AI, edits the repositories it reads from, runs a shell command,
allocates a runtime, executes a Work Package, performs recovery, or validates an
outcome (doc 11 *Architectural Boundaries*). The Harness is the permanent compilation
boundary between orchestration and execution.

Determinism is a hard requirement: given identical Harness Requests and identical
resolution sources, the Harness always produces identical Execution Packages,
Execution Manifests, and event streams. There is no AI and no randomness; identifiers
are pure functions of the Harness Request identities (no timestamps in identifiers).

Dependency direction is one-way: ``nexus_harness → {nexus_orchestration, nexus_infra,
nexus_core}``. It consumes Orchestration's Harness Requests by value/reference and
reuses the Phase 2 persistence mechanism without modifying it.
"""

from __future__ import annotations

from nexus_harness.artifact_resolver import (
    ArtifactResolver,
    ResolvedArtifact,
    ResolvedArtifacts,
)
from nexus_harness.capability_resolver import (
    CapabilityResolver,
    ResolvedCapabilities,
    ResolvedCapability,
)
from nexus_harness.composition import HarnessContext, build_harness
from nexus_harness.context_resolver import ContextResolver, ContextView
from nexus_harness.events import (
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
)
from nexus_harness.harness import HarnessRepositories, HarnessService
from nexus_harness.manifest_builder import ExecutionManifest, ExecutionManifestBuilder
from nexus_harness.package_builder import ExecutionPackage, ExecutionPackageBuilder
from nexus_harness.policy_resolver import PolicyBundle, PolicyResolver, ResolvedPolicy
from nexus_harness.requests import CompilationRequest, CompilationResult
from nexus_harness.skill_resolver import ResolvedSkill, ResolvedSkills, SkillResolver
from nexus_harness.sources import (
    HarnessSources,
    InMemoryCapabilityRegistry,
    InMemoryPolicyRegistry,
    InMemorySkillRegistry,
)
from nexus_harness.validator import HarnessValidator, ValidatedRequest
from nexus_harness.validators import (
    HarnessError,
    InvalidHarnessRequestError,
    PackageCompilationError,
    UnresolvedReferenceError,
    validate_outputs,
    validate_request_shape,
)
from nexus_harness.vocabulary import ManifestStatus, PackageStatus

__version__ = "2.5.0"

__all__ = [
    "ArtifactResolver",
    "CapabilityResolver",
    "CompilationRequest",
    "CompilationResult",
    "ContextResolver",
    "ContextView",
    "ExecutionManifest",
    "ExecutionManifestBuilder",
    "ExecutionPackage",
    "ExecutionPackageBuilder",
    "FixedTimestampSource",
    "HarnessContext",
    "HarnessError",
    "HarnessRepositories",
    "HarnessService",
    "HarnessSources",
    "HarnessValidator",
    "InMemoryCapabilityRegistry",
    "InMemoryPolicyRegistry",
    "InMemorySkillRegistry",
    "InvalidHarnessRequestError",
    "ManifestStatus",
    "PackageCompilationError",
    "PackageStatus",
    "PolicyBundle",
    "PolicyResolver",
    "ResolvedArtifact",
    "ResolvedArtifacts",
    "ResolvedCapabilities",
    "ResolvedCapability",
    "ResolvedPolicy",
    "ResolvedSkill",
    "ResolvedSkills",
    "SkillResolver",
    "SystemTimestampSource",
    "TimestampSource",
    "UnresolvedReferenceError",
    "ValidatedRequest",
    "build_harness",
    "validate_outputs",
    "validate_request_shape",
]
