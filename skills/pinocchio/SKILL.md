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

Each receipt has one verdict:
- **PASS**: the evidence supports every claim, or no claim was made.
- **FAIL**: the evidence contradicts a claim (for example, no test ran after your last edit).
- **CAN'T TELL**: Pinocchio could not confirm or refute a claim (for example, no recognized test
  command, no edits this session, or tests may have run in a subagent).

Modes (`mode` in the settings below):
- **default**: block on FAIL only; CAN'T TELL is reported, not blocked.
- **report**: never block; only show the receipt.
- **strict**: block on FAIL and on CAN'T TELL.
- **off**: do nothing.

At most `maxBlocksPerSession` blocks (default 2) happen in one session, then Pinocchio only reports.

When Pinocchio blocks you: do the missing step (usually run the tests), then report the actual
result. Never restate a claim without new evidence.

Settings live in `.claude/pinocchio.json`:
`{"mode":"default|report|strict|off","testCommands":["^make verify$"],"claimPhrases":{"tests":["ci is green"]},"maxBlocksPerSession":2,"commitLedger":false}`.
`PINOCCHIO=off` disables it for one session. The ledger is `.claude/pinocchio/ledger.jsonl`.
