---
name: pinocchio
description: Explains Pinocchio receipts (PASS / FAIL / CAN'T TELL) and how to configure claim checking. Use when a Pinocchio receipt or block appears, or the user asks about Pinocchio settings.
---

# Pinocchio

Pinocchio checks completion claims at every stop against evidence you did not produce:
- **stale-tests**: you said tests pass, but no test command ran after your last edit.
- **red-tests**: the last test run after your last edit failed (exit code, failure summary, or a fresh JUnit report).
- **phantom-edit**: you said you changed or fixed something, but no file changed.
- **tampering** (warning only): deleted tests, new skip markers, or removed assertions.

When Pinocchio blocks you: do the missing step (usually run the tests), then report the actual
result. Never restate a claim without new evidence.

Settings live in `.claude/pinocchio.json`:
`{"mode":"default|report|strict|off","testCommands":["^make verify$"],"claimPhrases":{"tests":["ci is green"]},"maxBlocksPerSession":2,"commitLedger":false}`.
`PINOCCHIO=off` disables it for one session. The ledger is `.claude/pinocchio/ledger.jsonl`.
