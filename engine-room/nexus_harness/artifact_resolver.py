"""Step 6 — Artifact Resolver (resolve required Artifacts; never modify them).

Resolves the input Artifacts a Work Package consumes — the references on
``WorkPackage.inputs`` whose target type is ``artifact`` — against the Artifact
repository, confirming each exists and carrying its immutable descriptor forward. The
Artifact is immutable by default (ADR-003); the Harness reads it and never writes,
advances, or revises it. An input Artifact reference that does not resolve is a
fail-closed error.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.domain.work_package import WorkPackage
from nexus_harness.sources import HarnessSources
from nexus_harness.validators import UnresolvedReferenceError
from nexus_harness.vocabulary import ARTIFACT_TARGET_TYPE


class ResolvedArtifact(ValueObject):
    """One resolved input Artifact — its reference plus immutable descriptor fields."""

    reference: Reference
    identity: str
    type: str
    status: str
    version: str


class ResolvedArtifacts(ValueObject):
    """The complete, deterministic set of input Artifacts resolved for one request."""

    artifacts: tuple[ResolvedArtifact, ...] = ()


class ArtifactResolver:
    """Resolves a Work Package's input Artifact references (read-only)."""

    def __init__(self, sources: HarnessSources) -> None:
        self._sources = sources

    def resolve(self, request_identity: str, work_package: WorkPackage) -> ResolvedArtifacts:
        """Resolve each ``artifact`` input (sorted by identity); fail closed on a miss."""
        references = sorted(
            (ref for ref in work_package.inputs if ref.target_type == ARTIFACT_TARGET_TYPE),
            key=lambda ref: ref.identifier,
        )
        return ResolvedArtifacts(
            artifacts=tuple(self._resolve(request_identity, ref) for ref in references)
        )

    def _resolve(self, request_identity: str, reference: Reference) -> ResolvedArtifact:
        artifact = self._sources.artifacts.get(reference.identifier)
        if artifact is None:
            raise UnresolvedReferenceError(
                f"artifact {reference.identifier!r} for harness request {request_identity!r} "
                f"is not resolvable"
            )
        return ResolvedArtifact(
            reference=Reference(target_type=ARTIFACT_TARGET_TYPE, identifier=artifact.identity),
            identity=artifact.identity,
            type=artifact.type.value,
            status=artifact.status.value,
            version=artifact.version,
        )
