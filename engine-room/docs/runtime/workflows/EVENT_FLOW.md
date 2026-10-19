# Event Flow & Replay -- Implementation

Every engine in the workflow appends to **one** authoritative, append-only event store (ADR-001).
Nothing mutates a prior event; state -- Runtime sessions, Knowledge items, projections -- is always
a fold over the log. This is what makes the whole workflow replayable (Milestone 4).

## One shared log, nine producers

`PipelineBuilder` gives every engine the same `InfrastructureContext`, so a single run's log
interleaves all producers in causal order. The reference workflow emits **111 events** across nine
producers:

```
context_engineering  planning  orchestration  harness  runtime  validation  recovery  reflection  knowledge
```

(Execution emits under the `runtime` producer namespace -- it drives the runtime session -- so the
ten engines surface as nine event producers.) Each event carries a deterministic identifier, the
operation `correlation_identifier` (INV-39), its producer, and a reference-only payload (INV-27).

## Replay = reconstruction from the log alone

`PipelineExecutor.replay()` calls `reconstruct(event_store.read_all())`, which rebuilds a
`ReplayTimeline` **without any live engine**:

- it walks the ordered log, grouping each contiguous run of same-producer events into a
  `ReplayStage` (producer, event types, correlation);
- it preserves the full ordered `event_ids`, `event_types`, and `producers`.

Because the log is the authoritative record, reconstruction is lossless *by construction*. The test
`test_replay_reconstructs_the_history_without_information_loss` asserts the reconstructed
`event_ids` and `event_types` equal the live run's events exactly, and that every participating
engine reappears as a producer.

## No information loss, deterministic replay

- **No loss:** `replay.event_ids == tuple(e.identifier for e in run.events)` -- the reconstruction
  is the log.
- **Deterministic:** two identical runs over independent pipelines yield byte-identical event
  streams (`test_full_pipeline_is_byte_identical_across_runs`), so replaying either reproduces the
  same operational timeline. Every id is a pure function of stable identity (INV-16); there is no
  clock or randomness in any decision path.
- **Idempotent substrate:** the event store dedupes by identifier (INV-16), so duplicate or
  out-of-order delivery cannot corrupt a replay.

## Append-only guarantee across the seam

The workflow only ever *appends*. The coordinator's two boundary adaptations
(Harness->Runtime projection, Reflection->Knowledge candidate) are pure value transforms that emit
no events themselves; the events they lead to (`runtime.*`, `knowledge.*`) are emitted by the
engines they feed. Reconstructing the log therefore always yields the complete, ordered history of
what actually happened.
