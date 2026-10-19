# Nexus v2.5.0 — Accountable Goal Execution

**Release:** stable minor, v2.5.0. **Title:** Nexus v2.5.0 — Accountable Goal Execution.

## Summary

Nexus v2.5.0 is a stable minor release adding an operator-supervised path across Phases 1–6: grounded goal
understanding and reviewable plans; constrained, explicitly approved first-party repository actions; independent
evidence validation; evidence-bound Knowledge; and a bounded technical operator pilot. Nexus v1 and v2 remain
independent. The release changes the shared distribution version only; it neither migrates v1 data nor changes v1
behavior.

## Pilot evidence

The controlled pilot used one operator identity and five synthetic, disposable fixture workspaces outside the
Nexus checkout. The frozen cases and results are recorded in the [Phase 6 release review](../phase6/RELEASE_REVIEW.md)
and the [pilot evidence bundle](../phase6/evidence/pilot/20260930-operator-pilot-01/scorecard.json).

| Case | Independent edit / test | Knowledge | Operator rating |
| --- | --- | --- | --- |
| P1 addition | passed / passed | accepted | useful |
| P2 normalization | passed / passed | accepted | useful |
| P3 clamp | passed / passed | accepted | useful |
| P4 deliberately incorrect title repair | failed / failed | rejected | not useful |
| P5 missing required JUnit report | passed / requires review | not promoted | not useful |

Three of five cases completed and were rated useful. One failed and one required review. The operator reported zero
false denials. The pilot recorded complete event lineage and no unauthorized action, false passed verdict, or
completed-run replay duplication. The SQLite and artifact-sidecar backup/restore record is included in the evidence
bundle; restore was verified at the same absolute fixture paths, with rollback copies retained.

The harness prepended `Fix software function:` to each frozen goal to satisfy the current deterministic Intent
route. This five-request intervention is recorded and limits what the pilot demonstrates: it does not show that
the unmodified requests resolve without help.

## Verification evidence

- Live-Claude strict suite: **3,261 passed**, `-W error`, zero skips and zero warnings.
- Ruff check, Phase 6 Ruff format check, Phase 6 mypy, and `uv build`: passed.
- Whole-repository Ruff format check: **55 existing findings outside Phase 6** remain disclosed in the
  [Phase 6 release review](../phase6/RELEASE_REVIEW.md).

The Phase 6 technical pilot gate passed. That gate is distinct from CI verification of the intended release tag.
The pilot used synthetic fixtures and does not establish arbitrary real-repository reliability, sustained operation,
or autonomous repair. The actions remain constrained to the
first-party path and its configured allow-list. No general provider-CLI governance claim is made.

## Compatibility and data

Phases 1–6 introduced no durable schema migration and added no schema-versioning or upgrade mechanism. The v2.5.0
version update does not convert or otherwise modify v1 data or behavior. This report makes no broader compatibility
claim than the evidence above supports.

## Release references

The GitHub release and tag identify the published commit. The Actions links show the CI runs; both workflows must
pass on the pushed release commit before the tag is published.

- Tag: [`v2.5.0`](https://github.com/STiFLeR7/nexus/tree/v2.5.0)
- GitHub release: [Nexus v2.5.0 — Accountable Goal Execution](https://github.com/STiFLeR7/nexus/releases/tag/v2.5.0)
- Core CI workflow: [core-ci.yml runs](https://github.com/STiFLeR7/nexus/actions/workflows/core-ci.yml)
- Nexus CI workflow: [ci.yml runs](https://github.com/STiFLeR7/nexus/actions/workflows/ci.yml)
