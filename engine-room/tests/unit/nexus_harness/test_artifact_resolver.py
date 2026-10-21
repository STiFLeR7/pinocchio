"""Unit tests for nexus_harness.artifact_resolver.

Covers ArtifactResolver.resolve(request_identity, work_package):
- Empty inputs → empty ResolvedArtifacts (no error).
- Non-artifact inputs (e.g. work_package refs) are silently ignored.
- Only refs whose target_type == "artifact" are resolved.
- Results are sorted by identity.
- Each ResolvedArtifact carries: reference (target_type="artifact"), identity,
  type (string), status (string), version.
- A missing artifact reference raises UnresolvedReferenceError.
- Multiple artifacts are all resolved.
- Resolve is deterministic: two calls return equal results.
- ResolvedArtifacts and ResolvedArtifact are frozen (mutations rejected).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.enums import ArtifactStatus, ArtifactType
from nexus_harness.artifact_resolver import ArtifactResolver, ResolvedArtifacts
from nexus_harness.validators import UnresolvedReferenceError
from nexus_harness.vocabulary import ARTIFACT_TARGET_TYPE
from tests.unit.nexus_harness.helpers import artifact, harness_env, ref, work_package

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolver(*artifacts_to_register) -> ArtifactResolver:
    """Return an ArtifactResolver pre-loaded with the given artifacts."""
    env = harness_env(artifacts=artifacts_to_register)
    return ArtifactResolver(env.harness.sources)


# ---------------------------------------------------------------------------
# Empty inputs
# ---------------------------------------------------------------------------


def test_empty_inputs_returns_empty_resolved_artifacts() -> None:
    resolver = _resolver()
    wp = work_package("wp-empty", inputs=())
    result = resolver.resolve("hreq-1", wp)

    assert isinstance(result, ResolvedArtifacts)
    assert result.artifacts == ()


def test_only_non_artifact_inputs_returns_empty() -> None:
    """Inputs whose target_type is not 'artifact' are completely ignored."""
    resolver = _resolver()
    wp = work_package(
        "wp-1",
        inputs=(
            ref("work_package", "other-wp"),
            ref("skill", "some-skill"),
            ref("context_package", "ctx-1"),
        ),
    )
    result = resolver.resolve("hreq-1", wp)
    assert result.artifacts == ()


# ---------------------------------------------------------------------------
# Single artifact
# ---------------------------------------------------------------------------


def test_single_artifact_input_is_resolved() -> None:
    art = artifact("art-1")
    resolver = _resolver(art)
    wp = work_package("wp-1", inputs=(ref("artifact", "art-1"),))
    result = resolver.resolve("hreq-1", wp)

    assert len(result.artifacts) == 1


def test_resolved_artifact_reference_target_type() -> None:
    art = artifact("art-ref")
    resolver = _resolver(art)
    wp = work_package("wp-1", inputs=(ref("artifact", "art-ref"),))
    result = resolver.resolve("hreq-1", wp)

    ra = result.artifacts[0]
    assert ra.reference.target_type == ARTIFACT_TARGET_TYPE
    assert ra.reference.identifier == "art-ref"


def test_resolved_artifact_identity_matches_source() -> None:
    art = artifact("art-ident")
    resolver = _resolver(art)
    wp = work_package("wp-1", inputs=(ref("artifact", "art-ident"),))
    result = resolver.resolve("hreq-1", wp)

    assert result.artifacts[0].identity == "art-ident"


def test_resolved_artifact_type_is_string() -> None:
    art = artifact("art-type", artifact_type=ArtifactType.SOURCE)
    resolver = _resolver(art)
    wp = work_package("wp-1", inputs=(ref("artifact", "art-type"),))
    result = resolver.resolve("hreq-1", wp)

    ra = result.artifacts[0]
    assert ra.type == "source"
    assert isinstance(ra.type, str)


def test_resolved_artifact_status_is_string() -> None:
    art = artifact("art-status", status=ArtifactStatus.DRAFT)
    resolver = _resolver(art)
    wp = work_package("wp-1", inputs=(ref("artifact", "art-status"),))
    result = resolver.resolve("hreq-1", wp)

    ra = result.artifacts[0]
    assert ra.status == "draft"
    assert isinstance(ra.status, str)


def test_resolved_artifact_version_matches_source() -> None:
    art = artifact("art-v", version="99")
    resolver = _resolver(art)
    wp = work_package("wp-1", inputs=(ref("artifact", "art-v"),))
    result = resolver.resolve("hreq-1", wp)

    assert result.artifacts[0].version == "99"


def test_resolved_artifact_documentation_type() -> None:
    art = artifact("art-doc", artifact_type=ArtifactType.DOCUMENTATION)
    resolver = _resolver(art)
    wp = work_package("wp-1", inputs=(ref("artifact", "art-doc"),))
    result = resolver.resolve("hreq-1", wp)

    assert result.artifacts[0].type == "documentation"


def test_resolved_artifact_published_status() -> None:
    art = artifact("art-pub", status=ArtifactStatus.PUBLISHED)
    resolver = _resolver(art)
    wp = work_package("wp-1", inputs=(ref("artifact", "art-pub"),))
    result = resolver.resolve("hreq-1", wp)

    assert result.artifacts[0].status == "published"


# ---------------------------------------------------------------------------
# Multiple artifacts
# ---------------------------------------------------------------------------


def test_multiple_artifacts_all_resolved() -> None:
    art_a = artifact("art-a")
    art_b = artifact("art-b")
    art_c = artifact("art-c")
    resolver = _resolver(art_a, art_b, art_c)
    wp = work_package(
        "wp-1",
        inputs=(
            ref("artifact", "art-a"),
            ref("artifact", "art-b"),
            ref("artifact", "art-c"),
        ),
    )
    result = resolver.resolve("hreq-1", wp)

    assert len(result.artifacts) == 3
    identities = {ra.identity for ra in result.artifacts}
    assert identities == {"art-a", "art-b", "art-c"}


def test_results_sorted_by_identity() -> None:
    """Resolved artifacts are sorted by identity regardless of input order."""
    art_z = artifact("art-z")
    art_a = artifact("art-a")
    art_m = artifact("art-m")
    resolver = _resolver(art_z, art_a, art_m)
    wp = work_package(
        "wp-1",
        inputs=(
            ref("artifact", "art-z"),
            ref("artifact", "art-a"),
            ref("artifact", "art-m"),
        ),
    )
    result = resolver.resolve("hreq-1", wp)

    identities = [ra.identity for ra in result.artifacts]
    assert identities == sorted(identities)


# ---------------------------------------------------------------------------
# Mixed artifact and non-artifact inputs
# ---------------------------------------------------------------------------


def test_mixed_inputs_only_artifacts_resolved() -> None:
    """Only artifact-typed inputs are resolved; other target types are ignored."""
    art = artifact("art-1")
    resolver = _resolver(art)
    wp = work_package(
        "wp-mixed",
        inputs=(
            ref("work_package", "other"),
            ref("artifact", "art-1"),
            ref("skill", "some-skill"),
        ),
    )
    result = resolver.resolve("hreq-1", wp)

    assert len(result.artifacts) == 1
    assert result.artifacts[0].identity == "art-1"


# ---------------------------------------------------------------------------
# Fail-closed on missing artifact
# ---------------------------------------------------------------------------


def test_missing_artifact_raises_unresolved_reference_error() -> None:
    """A ref to a non-existent artifact is a hard fail-closed error."""
    resolver = _resolver()  # empty store
    wp = work_package("wp-1", inputs=(ref("artifact", "does-not-exist"),))

    with pytest.raises(UnresolvedReferenceError):
        resolver.resolve("hreq-1", wp)


def test_missing_artifact_error_mentions_identity() -> None:
    resolver = _resolver()
    wp = work_package("wp-1", inputs=(ref("artifact", "missing-art"),))

    with pytest.raises(UnresolvedReferenceError, match="missing-art"):
        resolver.resolve("hreq-1", wp)


def test_partial_resolution_fails_closed() -> None:
    """If one of several artifact inputs is missing, the whole call raises."""
    art = artifact("art-present")
    resolver = _resolver(art)
    wp = work_package(
        "wp-1",
        inputs=(
            ref("artifact", "art-present"),
            ref("artifact", "art-absent"),
        ),
    )
    with pytest.raises(UnresolvedReferenceError):
        resolver.resolve("hreq-1", wp)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_resolve_is_deterministic() -> None:
    """Two calls on identical inputs produce equal results."""
    art = artifact("art-det")
    resolver = _resolver(art)
    wp = work_package("wp-1", inputs=(ref("artifact", "art-det"),))

    result_1 = resolver.resolve("hreq-1", wp)
    result_2 = resolver.resolve("hreq-1", wp)

    assert result_1 == result_2


def test_determinism_with_multiple_artifacts() -> None:
    art_a = artifact("art-a")
    art_b = artifact("art-b")
    resolver = _resolver(art_a, art_b)
    wp = work_package(
        "wp-det",
        inputs=(ref("artifact", "art-b"), ref("artifact", "art-a")),
    )

    result_1 = resolver.resolve("hreq-1", wp)
    result_2 = resolver.resolve("hreq-1", wp)

    assert result_1 == result_2
    assert [ra.identity for ra in result_1.artifacts] == ["art-a", "art-b"]


# ---------------------------------------------------------------------------
# Frozen value objects
# ---------------------------------------------------------------------------


def test_resolved_artifacts_is_frozen() -> None:
    art = artifact("art-frz")
    resolver = _resolver(art)
    wp = work_package("wp-1", inputs=(ref("artifact", "art-frz"),))
    result = resolver.resolve("hreq-1", wp)

    with pytest.raises(ValidationError):
        result.artifacts = ()  # type: ignore[misc]


def test_resolved_artifact_is_frozen() -> None:
    art = artifact("art-frz2")
    resolver = _resolver(art)
    wp = work_package("wp-1", inputs=(ref("artifact", "art-frz2"),))
    result = resolver.resolve("hreq-1", wp)
    ra = result.artifacts[0]

    with pytest.raises(ValidationError):
        ra.identity = "mutated"  # type: ignore[misc]
