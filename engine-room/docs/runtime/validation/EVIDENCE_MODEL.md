# Evidence Model — implementation

Evidence is **produced by Validation** (INV-12): Execution emits Evidence *Candidates*;
Validation inspects them and promotes each into an immutable :class:`Evidence` value that is
*observable, repeatable, independent, traceable, auditable* (doc 14 *Evidence Model*).

---

## 1. The `Evidence` value object

Immutable (frozen pydantic). References its subject **by id**; never embeds artifact content
(INV-12, ADR-003).

| Field | Meaning |
|---|---|
| `identity` | deterministic id `ev-{session}-{source}-{seq}` |
| `source` | `EvidenceSource` — where it came from |
| `kind` | provider-neutral kind label |
| `subject_ref` | the artifact/session it is about, **by id** |
| `observed` | a small deterministic descriptor (e.g. `exit_status`, `length`, `outcome`) — never the payload |
| `derived_from` | provenance: the event/result refs the fact was read from (auditability) |
| `correlation_identifier` | the operation's correlation (shared lineage) |

## 2. Evidence sources (Milestone 1)

| `EvidenceSource` | Collector | Read from | Independent of self-report? |
|---|---|---|---|
| `ARTIFACT` | `ArtifactInspector` | `runtime.artifact_emitted` **events** in the log | **Yes** — the log, not the result |
| `STDOUT` / `STDERR` | `OutputCollector` | captured output (structural descriptor: length, lines) | partial (execution output) |
| `STRUCTURED_OUTPUT` | `OutputCollector` | captured structured output (count, length) | partial |
| `RUNTIME_METADATA` | `MetadataCollector` | outcome, final state, exit status, error, cleanup, runtime | it *records* the self-report as a fact, but never treats it as proof |
| `EXECUTION_METRIC` | `MetadataCollector` | `ExecutionResult.metrics` | partial |

**Why artifacts come from the event log, not the result.** Doc 14 says Evidence "should
never rely *solely* on execution output," and INV-20 forbids trusting the runtime's
self-report. Artifact Evidence is therefore read from the independent `runtime.artifact_emitted`
**events** (the append-only log), so the corroboration rule (`VALIDATION_RULES.md`) rests on
an independent record, not on a field the runtime populated about itself.

## 3. Immutability & determinism

- Evidence is frozen; a "revision" would be a new object, never a mutation.
- Ids are pure functions of the session identity + source + ordinal → identical executions
  yield identical Evidence sets (`test_collector.py::test_collector_is_deterministic`).
- The collector never duplicates artifact content: an artifact Evidence carries the
  artifact `Reference` and a `{artifact, kind}` descriptor; output Evidence carries only
  structural counts (length/lines/count). The raw bytes stay behind their reference.

## 4. Traceability

Every Evidence records `derived_from` (the event or result reference it was read from) and
the shared `correlation_identifier`, so any verdict is traceable Report → Evidence →
source event → the whole Goal lineage. The Report references Evidence by id (never embeds
it), closing the chain without duplication.
