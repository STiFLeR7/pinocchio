# Execution Flow — from a Ready session to a Destroyed one

The Execution Engine (`nexus_execution/engine.py`) **performs** what RM **prepared**
(doc `00` §1/§8). It is generic: it imports no provider and branches on none.

---

## 1. The end-to-end pipeline (the success scenario)

```
Execution Package
   │  projected at the integration boundary (requests.py)
   ▼
RuntimeIntake ──▶ Runtime Manager.prepare(...)          [nexus_runtime, already built]
                     └─ session_created → candidates_resolved → capabilities_matched
                        → allocated → prepared → ready         (session state: Ready)
   │  handoff (the Ready RuntimeSession)
   ▼
Execution Engine.execute(session, adapter, work_package)   [nexus_execution]
   │
   ├─ C  Ready → Running          emit runtime.started
   ├─ D  each output chunk        emit runtime.output   {channel, sequence, length}   (content by capture, not in event)
   ├─ E  each progress update     emit runtime.progress {phase, fraction|"unknown", milestone}
   ├─ F  each artifact            emit runtime.artifact_emitted {artifact_ref, kind}   (by reference)
   ├─ (G) cancel / (10) timeout   emit runtime.timed_out; enforce stop
   ├─ F  captured stdout/stderr   emit runtime.artifact_emitted {captured-output}      (by reference)
   ├─ H  finalize terminal        Running → Completed | Cancelled | Failed
   │        emit runtime.completed | runtime.cancelled | runtime.failed
   └─ I  adapter.cleanup()        → Destroyed;  emit runtime.destroyed {outcome, cleanup_ok}
   │
   ▼
ExecutionResult  (outcome, final_state=Destroyed, artifact_refs, event_ids, captured stdout/stderr, metrics)
```

Two arrows through one stack: RM prepares *down to* `Ready`; the Engine performs *through*
the adapter into the runtime. Every `runtime.*` event uses RM's deterministic
`ids.event_id(scope, kind, sequence)` scheme, so a run replays identically under a fixed
clock.

## 2. Signal → event → state (the fold)

| Adapter signal | Engine event (`15`) | Drives state (`07`) |
|---|---|---|
| — (start) | `runtime.started` | `Ready → Running` |
| `OutputSignal` | `runtime.output` | — (non-lifecycle) |
| `ProgressSignal` | `runtime.progress` | — |
| `ArtifactSignal` | `runtime.artifact_emitted` | — |
| (deadline exceeded) | `runtime.timed_out` | — (precedes fail) |
| `TerminalSignal(COMPLETED)` | `runtime.completed` | `Running → Completed` |
| `TerminalSignal(CANCELLED)` | `runtime.cancelled` | `Running → Cancelled` |
| `TerminalSignal(FAILED)` | `runtime.failed` | `Running → Failed` |
| (cleanup) | `runtime.destroyed` | `* → Destroyed` |

The final session state is a **projection** of this stream (ADR-001): folding the full
event-type stream (preparation + execution) with `project_state(...)` yields `Destroyed` —
asserted end-to-end in `tests/integration/…`.

## 3. Cancellation & timeout (doc 09 / doc 10)

- **Cancellation** is cooperative *and* enforced: the adapter checks `ExecutionControl.cancelled`
  between signals; the engine also stops consuming once cancelled and synthesizes a
  `Cancelled` terminal, so an uncooperative adapter cannot run past a cancel.
- **Timeout** is a deterministic `deadline_steps` bound (a clock-free model of `10`): when the
  consumed-signal count exceeds it, the engine emits `runtime.timed_out` and finalizes
  `Failed` (`error_class="timeout"`). Production substitutes a wall-clock deadline; the
  semantics are identical.

## 4. Error model (doc 11)

- An adapter-reported `FAILED` terminal carries a doc-11 `error_class` and `owner`.
- An adapter raising an `ExecutionError` subclass is classified by that class.
- Any other adapter exception is classified as `provider-failure` (the provider crashed).
- A cleanup failure is surfaced (`cleanup_ok=False`) but the session still reaches
  `Destroyed` (`07` §6) — the leak/anomaly is recorded, never hidden.

## 5. Evidence discipline (INV-12 / ADR-003)

Events never embed artifact content: `runtime.output` carries `{channel, sequence, length}`;
`runtime.artifact_emitted` carries a `{artifact_ref, kind}`. Captured stdout/stderr is
additionally surfaced as a `captured-output` **artifact reference**. The raw captured text
is returned only on the in-process `ExecutionResult` for the caller/tests — never inside an
event or persisted Evidence.
