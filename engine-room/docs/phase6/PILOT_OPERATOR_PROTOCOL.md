# Phase 6 technical operator pilot protocol

The frozen case set is in [cases.json](cases.json). This pilot changes disposable fixture workspaces only. Store the SQLite database and its `.action_artifacts` sidecar outside each governed workspace. Restore is supported only to the same absolute fixture paths; moving the pair elsewhere invalidates recorded artifact paths.

## Review and approval

Choose one unique `RUN_ID` for the entire five-case pilot, one empty disposable `WORKSPACE_ROOT`, and one external `DB` path. Reuse the same `RUN_ID` and database for P1–P5; use a separate workspace directory named for each case. Run prepare for each case:

```powershell
.venv\Scripts\python.exe scripts\phase6_pilot.py prepare --case-id P1 --run-id RUN_ID --workspace WORKSPACE_ROOT\P1 --db DB
```

Inspect `DB.phase6/P1/plan_review.json`. It shows the actual proposed diff, test samples, frozen SHA/JUnit conditions, dependency, source references, and the assumptions/limitations. P4 is intentionally incorrect; P5 intentionally omits its JUnit report. Prepare stops after Planning and checks that no action started and no workspace bytes changed.

Only after review, run approval in a separate process:

```powershell
.venv\Scripts\python.exe scripts\phase6_pilot.py approve --case-id P1 --run-id RUN_ID --workspace WORKSPACE_ROOT\P1 --db DB --operator OPERATOR_ID
```

The command prints the prepared review again and asks for the exact word `APPROVE`; any other input denies the write. It then runs the dependent fixed test action. Never use `--simulate-approval` for the human pilot.

Run fresh-process replay and inspect the result:

```powershell
.venv\Scripts\python.exe scripts\phase6_pilot.py replay --case-id P1 --run-id RUN_ID --workspace WORKSPACE_ROOT\P1 --db DB
```

Replay must add no action/runtime/validation event and must retain the same verdicts. After reviewing the result, record the operator assessment:

```powershell
.venv\Scripts\python.exe scripts\phase6_pilot.py assess --case-id P1 --run-id RUN_ID --db DB --operator OPERATOR_ID
```

`assess` records `USEFUL` or `NOT_USEFUL` and an optional reason under `docs/phase6/evidence/pilot/RUN_ID/`. Assessments are not inferred from a passing test. Repeat the sequence for P2–P5 with the same database and separate workspaces; keep all five cases in the denominator, including failures, clarification, and unknown evidence.

After all five cases have been replayed and assessed, produce the denominator-based human scorecard:

```powershell
.venv\Scripts\python.exe scripts\phase6_pilot.py scorecard --run-id RUN_ID --workspace-root WORKSPACE_ROOT --db DB
```

## Backup and restore

Before pilot runs, preserve SQLite using its online backup API and copy the complete `.action_artifacts` sidecar while the pipeline is quiescent. Record both source and backup hashes. Restore both to the same checked absolute paths; verify every durable artifact reference resolves and matches its recorded SHA-256 before resuming or replaying. Keep the pre-restore pair intact until verification succeeds. On a failed restore, put the pre-restore pair back and stop for reconciliation. The automated rehearsal exercises this rollback path with disposable data; it does not qualify as human approval or operator assessment.

## Automated rehearsal boundary

Run `.venv\Scripts\python.exe scripts\phase6_pilot.py rehearse` to execute all five cases in temporary workspaces with simulated approvals. The output is explicitly labeled `automated_rehearsal`, with `human_pilot: false` and `release_gate_complete: false`. It is engineering evidence only. Release assessment still requires the actual named operator's five recorded assessments and the frozen gate thresholds.

The current deterministic Intent route requires the harness prefix `Fix software function:`. The report preserves each frozen goal verbatim and records this transformation. Treat it as an operator-input intervention/limitation, not evidence that the unmodified request text passed.
