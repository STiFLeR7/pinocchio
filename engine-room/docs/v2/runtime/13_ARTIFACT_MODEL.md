# 13 — Artifact Model

**Status:** design only. Defines how runtimes emit **artifacts** — files, logs, metrics,
structured outputs, and execution metadata — **runtime-independently**, so the same model
serves Claude Code, Gemini CLI, Shell, Docker, Browser, Python, MCP, remote workers, and
runtimes not yet imagined. Everything a runtime emits is an **Evidence Candidate**,
referenced by id and associated with the Runtime Session (`02`). RM **collects and
associates**; it **never grades, mutates, or validates**.

---

## 1. Principles (binding)

- **Everything emitted is an Evidence Candidate, by reference (INV-12, ADR-003).**
  A runtime never embeds its output in an event or in the session. It emits a
  **candidate** that is referenced **by id**; the bytes live elsewhere (§5). RM holds the
  reference, not the content.
- **RM collects, Validation grades (INV-20).** Runtimes produce *candidates*. **Validation**
  (a later phase) promotes Evidence Candidates → Evidence and renders the completion
  verdict. RM only **associates** candidates with the session and emits the
  `runtime.artifact_emitted` event. RM **never** declares an artifact good, complete, or
  validating of the work.
- **Immutable.** An artifact is **immutable by default** (the canonical `Artifact` domain
  object, `artifact.py`): a revision is a **new version** in the immutable version chain,
  never an overwrite. **RM never mutates an artifact** — not its content, not its status.
- **Runtime-independent.** A file from a shell, a metric from a container, a structured
  result from MCP, a screenshot from a browser all become the **same** referenced-candidate
  shape via the **Runtime Adapter** (`03`). Provider specifics stop at that boundary.
- **Event-sourced (ADR-001).** Each emission is a canonical `runtime.artifact_emitted`
  event (`15`); the session's **artifact set** is a **projection** of that stream (`02`
  §5). Replay reproduces the identical set (INV-16).
- **Recorded, not decided.** Emission records the external fact "the runtime produced
  this." It encodes no verdict.

## 2. The canonical Artifact object (already exists)

RM does not invent an artifact type. The platform's `Artifact` domain object
(`nexus_core/domain/artifact.py`, contract `artifact.md`, ADR-003) is the single shape;
runtime emissions map onto it. Fields RM/the adapter populate or reference (it does not
overwrite Validation-owned fields):

| `Artifact` field | Runtime-emission meaning |
|---|---|
| `identity` | the stable id the candidate is referenced by (INV-12) |
| `type` (`ArtifactType`) | the artifact category (§3) — one of `source`, `documentation`, `research`, `operational`, `communication`, `knowledge` |
| `producer` | the runtime/adapter that produced it (e.g. the runtime identity) |
| `owner` | the layer that owns it through its lifecycle (RM/Execution during the run) |
| `status` (`ArtifactStatus`) | starts in an emission-time status (`draft`/`generated`); **`validated` is set by Validation, never RM** |
| `lineage` | the provenance chain Goal → Plan → Work Package → Execution → Artifact (§4) |
| `correlation_identifier` | the operation-wide correlation shared with the session's events (INV-39) |
| `evidence_ref` | reference(s) **by id** to Evidence — populated by Validation, never embedded by RM (INV-12) |
| `created_time` / `version` / `parent_version` | recorded data; a revision is a new version, never an overwrite |

> `status` is a **derived projection, never authoritative** (per `artifact.py`). RM emits
> a candidate at `draft`/`generated`; only Validation advances it to `validated`. RM
> writing `validated` would be grading — forbidden (INV-20).

## 3. Artifact kinds and how each maps onto the model

Five runtime-emitted **kinds** are defined. The *kind* is the conceptual category the
adapter assigns; it maps onto the canonical `ArtifactType` and a referenced location:

| Kind | What it is | Maps onto `ArtifactType` | Referenced as |
|---|---|---|---|
| **file** | a produced/changed file or directory (code, doc, image, build output) | `source` / `documentation` (per content) | a content reference (path/handle/blob id) |
| **log** | a finalized run log (the immutable whole behind the live stream, `08` §5) | `operational` | a log-content reference |
| **metric** | a measured value or measurement set (duration, exit code, resource use, counts) | `operational` | a metric-record reference |
| **structured-output** | a typed machine-readable result the runtime emits (JSON result, tool result) | `operational` / `research` (per content) | a structured-record reference |
| **execution-metadata** | facts about the run itself (runtime identity, config used minus secrets, attempt) | `operational` | a metadata-record reference |

- The **kind** is a runtime-facing convenience the adapter assigns; the **`ArtifactType`**
  is the canonical taxonomy the domain object carries. The adapter performs the mapping;
  RM core does not interpret content.
- **execution-metadata never contains secrets** — credentials are referenced, never
  embedded (`17`); the same rule that keeps secrets out of events keeps them out of
  artifacts.
- A **log artifact** is the durable counterpart of the live log stream (`08` §5): the same
  output appears live as `runtime.output` and is finalized as an immutable log artifact.

## 4. Provenance, lineage & correlation

- **Lineage.** Each emitted artifact carries the `Artifact.lineage` provenance chain
  (Goal → Plan → Work Package → Execution → Artifact), so any output is traceable back to
  the Work Package that produced it and forward into Knowledge later.
- **Correlation.** The artifact's `correlation_identifier` is the **same** operation-wide
  correlation carried by the session and all its `runtime.*` events (INV-39), so a single
  Goal's full lineage — Goal → Context → Plan → Orchestration → Harness → **Runtime
  (artifacts)** — is one queryable causal stream.
- **Causation.** The `runtime.artifact_emitted` event may carry `causation_identifier`
  (`15` §3) linking the emission to the output/step that produced it, preserving
  cause→effect across the run.
- **Session association.** The artifact reference is accumulated on the session's artifact
  set (`02` §8). Across retries, each attempt is its own session but all share the
  correlation lineage (`02` §6), so the full artifact history of a package — across
  attempts — is one stream.

## 5. Where artifacts live vs. how they are referenced

- **RM holds references, not bytes.** The session, the events, and RM core all carry the
  artifact **id / handle** only (INV-12, ADR-003). The **content lives elsewhere** — a
  workspace, an object store, a container volume, an external system — wherever the
  producing runtime/adapter places it.
- **The reference is stable and addressable** (`Artifact.identity`), so Validation,
  Observability (`16`), and Knowledge (future) can discover and fetch the content later
  without RM ever having moved or copied the bytes.
- **RM never copies, rewrites, or relocates content** to "tidy" it — doing so would mutate
  provenance. If content must be finalized (e.g. a streaming log becoming a whole-log
  artifact, `08` §5), that finalization is the adapter's, and it produces a **new**
  immutable artifact, never an in-place edit.

```
runtime produces output            adapter (03)                 RM core (generic)
────────────────────────           ────────────                 ─────────────────
file / log / metric /     ─ place content somewhere ─▶ candidate id ─▶ runtime.artifact_emitted
structured / metadata        (workspace/store/volume)   (by reference)   event → session
                                                                          artifact-set projection
                             RM never holds the bytes — only the id (INV-12)
```

## 6. The `runtime.artifact_emitted` event

- Emitted (`15`) **when a runtime, through its adapter, produces an Evidence Candidate**.
  Illustrative payload (not a schema): `session`, `artifact_ref` (by id), `kind`.
- It is a canonical `Event` (`producer = "runtime"`, deterministic id, recorded timestamp,
  shared correlation — `15` §1), idempotent (INV-16) and sequence-ordered on the session
  timeline alongside output (`08`) and progress (`12`).
- It is a **record of emission, not a verdict**. `runtime.completed` (`07`/`15`) may carry
  the final `artifact_refs`, but neither event asserts the work succeeded — that is
  Validation's (INV-20). Validation consumes `runtime.artifact_emitted` to discover
  candidates (`15` §5).

## 7. Per-runtime artifact emission (comparison)

How each runtime typically emits each kind. All of it is normalized to the same
referenced-candidate shape by that runtime's adapter (`03`); RM core sees only the id.

| Runtime | file | log | metric | structured-output | execution-metadata |
|---|---|---|---|---|---|
| **Shell** | files written to cwd | finalized stdout/stderr log | exit code, duration | (rare) | command, cwd, exit |
| **Docker** | files in mounted volumes | container log | exit code, resource stats | container events | image, container id, exit |
| **Claude Code** | files it edited/created | session log | tokens/turns counts | tool results as structured | model/session metadata |
| **Python** | files the script wrote | process log | timing, return code | typed result records | interpreter/script metadata |
| **Browser** | downloads, screenshots | console/network log | timing, page metrics | DOM/extraction results | session/driver metadata |
| **MCP** | resources the server wrote | transport log | call timing | JSON-RPC results as structured | server/tool metadata |
| **Remote worker** | files relayed from the worker | relayed worker log | relayed metrics | relayed structured results | worker/transport metadata |

Reading the table: a sparse column (e.g. Shell rarely emits structured-output) is
**normal**. The model requires no particular kind from any runtime; RM records whatever
the adapter emits, as immutable candidates by reference.

## 8. What the artifact model is *not*

- Not a grading mechanism — **RM never decides an artifact is good or validating**;
  Validation promotes Candidates → Evidence and renders the verdict (INV-20).
- Not a completion signal — emitting artifacts, even many, does not mean the work
  succeeded; `Completed` is process-end (`07`), success is Validation's.
- Not a byte store — RM holds references; content lives elsewhere (§5).
- Not mutable — artifacts are immutable; a change is a new version, never an overwrite;
  **RM never mutates an artifact** (§1).
- Not embedded Evidence — Evidence is referenced by id, never inlined (INV-12).

## 9. Cross-references

`00` (overview, Evidence-by-reference invariants) · `01` (supervision step 13:
collect artifacts) · `02` (session artifact-set, association, retries) · `03` (adapter
normalization) · `07` (`Completed` ≠ validated) · `08` (stream-to-artifact boundary,
log artifacts) · `12` (artifact emission as a progress/liveness signal) ·
`15` (`runtime.artifact_emitted`, `runtime.completed`) · `16` (artifacts in telemetry) ·
`17` (no secrets in artifacts) · `19` (adding a runtime without changing the model) ·
ADR-003 / INV-12 / INV-20 (canonical model, Evidence by reference, completion verdict) ·
`nexus_core/domain/artifact.py` (the canonical `Artifact` object).
