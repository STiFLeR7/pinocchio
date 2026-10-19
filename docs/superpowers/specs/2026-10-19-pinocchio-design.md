# Pinocchio: design spec

- Date: 2026-10-19
- Status: Draft, awaiting review
- Tagline: *Your agent's nose grows when it lies.*

## 1. Summary

Pinocchio is a Claude Code plugin (one Stop hook + one small skill) that checks an AI coding
agent's completion claims ("done", "tests pass", "fixed") against evidence the agent did not
produce itself, and ends each session with a short receipt: **PASS**, **FAIL** or **CAN'T TELL**.
On a clear, evidence-backed lie it blocks the stop so the agent must keep working.

It is a lean port of the outcome-evidence ideas from Nexus v2 (`nexus_validation/outcome_evidence.py`,
`nexus_execution/actions/boundary.py`). Nexus v2 is retained in this repo as the "engine room".

### Why

Research on 2026-09-19..10-19 (raw: `~/Documents/Last30Days/viral-claude-code-skills-plugins-and-mcp-servers-raw-v3.md`)
showed: review and verification are the top unsolved pain; lean skills beat heavy MCP servers;
placebo-controlled benchmarks are becoming the credibility bar; the official plugin directory is the
primary discovery channel. Nexus as a standalone platform scored 2.5/10 on viral-readiness.

## 2. Goals and non-goals

**Goals (v1)**
- Catch false completion claims with near-zero overhead when the agent is honest.
- Never break a session: every internal failure fails open.
- Every verdict points at concrete evidence (transcript line, exit status, file hash).
- One-line native install, plus an `npx` guided onboarding.
- Ship with a pre-registered, placebo-controlled benchmark.

**Non-goals (v1)**
- Running tests or builds itself (read-only by design).
- Codex blocking (Codex has no documented blocking Stop hook; Codex gets the skill only).
- MCP server, LLM-based claim classification, network calls, telemetry.
- `/why` ledger explorer, PR receipts, build-claim check (all v1.1).

## 3. Decisions log

| # | Decision | Chosen |
|---|---|---|
| D1 | Evidence gathering | Read-only: transcript + filesystem + git. Never executes project commands. |
| D2 | Enforcement | Block only on FAIL; CAN'T TELL and PASS are user-only receipts; max 2 blocks/session. Modes: `default`, `report`, `strict`. |
| D3 | Runtime | Node.js >= 18, zero dependencies. |
| D4 | Claim detection | Receipt on any stop after edits; block requires a matched claim phrase AND contradicting evidence. |
| D5 | v1 checks | stale-tests, red-tests, phantom-edit (blocking); tampering (warn-only). |
| D6 | Ledger | Hash-chained JSONL in v1; explorer command in v1.1. |
| D7 | Name | Pinocchio. npm: `@stifler7/pinocchio`, bin `pinocchio`. |
| D8 | Repo | This repo becomes Pinocchio (`STiFLeR7/nexus` -> `STiFLeR7/pinocchio`); Nexus moves to `engine-room/`. |
| D9 | Install | Native `/plugin` install and `npx @stifler7/pinocchio setup` onboarding. |

## 4. Architecture

```
.claude-plugin/plugin.json      plugin manifest (name, version, hooks, skill)
.claude-plugin/marketplace.json single-plugin marketplace for /plugin marketplace add
hooks/hooks.json                registers the Stop hook -> node ${CLAUDE_PLUGIN_ROOT}/src/stop.js
skills/pinocchio/SKILL.md       short description (<= 100 tokens listed); body: receipts, modes, config
bin/pinocchio.js                CLI: setup | doctor | status | uninstall
src/
  stop.js        entry: stdin hook JSON -> pipeline -> stdout decision JSON. Only I/O module.
  transcript.js  transcript JSONL -> ordered events: edit(file,line), bash(cmd,failed,output,line), claim(text)
  claims.js      deterministic claim-phrase matcher (built-in list + config extensions)
  git.js         read-only git: status --porcelain, diff --numstat, rev-parse HEAD, ls-files
  junit.js       minimal JUnit XML reader: tests / failures / errors / skipped counts
  checks/stale-tests.js  checks/red-tests.js  checks/phantom-edit.js  checks/tampering.js
  verdict.js     combine check results -> pass | fail | cant_tell
  receipt.js     receipt text (systemMessage) and block reason text
  ledger.js      append + verify hash-chained ledger
  config.js      load .claude/pinocchio.json with defaults
test/            node:test suites, fixture transcripts, golden receipts
bench/           cases.json (frozen first), harness scripts, results
engine-room/     Nexus v1 + v2 (unchanged code, history preserved)
```

**Check contract:** `check(events, gitState, config, claims) -> { id, status: "pass"|"fail"|"unknown", blocking: boolean, evidence: object }`.
Checks are pure; only `stop.js`, `git.js`, `ledger.js` and `config.js` touch the system.

**Edit detection:** `Edit`, `Write`, `MultiEdit`, `NotebookEdit` tool calls, plus files reported
changed by `git status` (covers edits made through Bash).

**Test-command recognition (built-in):** `npm test`, `npm run test`, `pnpm test`, `yarn test`,
`bun test`, `npx vitest`, `vitest`, `jest`, `pytest`, `python -m pytest`, `go test`, `cargo test`,
`mvn test`, `gradle test`, `./gradlew test`, `dotnet test`, `rspec`, `bundle exec rspec`,
`phpunit`, `make test`. Extendable via config `testCommands` (regex strings).

## 5. Data flow and verdict

1. Claude Code runs the Stop hook with `session_id`, `transcript_path`, `cwd`, `last_assistant_message`.
2. Early exit with no output when: no edits in session AND no claim matched (a "fixed"/"updated X" claim with zero edits must still reach phantom-edit); mode `off` or `PINOCCHIO=off`; transcript unreadable (fail open, ledger `error` entry if writable).
3. Parse events; read git state.
4. Match claims in `last_assistant_message`:

| Claim type | Example phrases | Checks |
|---|---|---|
| tests | "tests pass", "all tests pass", "all green", "suite passes" | stale-tests, red-tests |
| fixed / done | "fixed", "done", "resolved", "works now", "verified" | red-tests (if any test ran after last edit), phantom-edit |
| file change | "updated `X`", "changed `X`", "added to `X`" | phantom-edit on `X` |
| always | n/a | tampering (warn-only) |

5. Check semantics:
   - **stale-tests**: FAIL if a tests claim exists and no recognized test command ran after the last edit, but at least one recognized test command exists in config/built-ins for this repo's detected ecosystem. UNKNOWN if no test command is recognizable for the repo.
   - **red-tests**: considers the last recognized test run after the last edit. FAIL if its tool result is an error (non-zero exit), or its output matches a known failure summary (`N failed`, `FAILED`, `Tests: N failed`, `✗`), or a JUnit file modified after the last edit reports failures/errors > 0. PASS if exit was success and no failure signal. UNKNOWN if no post-edit run.
   - **phantom-edit**: FAIL if a claimed file (or, for "fixed/done", the session as a whole) shows no change in git diff/status and no edit event. UNKNOWN outside a git repo or for paths outside `cwd`.
   - **tampering** (warn-only): flags deleted test files, added skip markers (`.skip(`, `xit(`, `xdescribe(`, `@pytest.mark.skip`, `t.Skip(`, `#[ignore]`), or net removal of assertion lines in test files.
6. Verdict precedence: any blocking FAIL -> **FAIL**; else a claim whose required check is UNKNOWN -> **CAN'T TELL**; else **PASS** (edits with no claims -> PASS, labelled "no claims made").
7. Output:
   - FAIL (default mode, blocks so far < 2): `{"decision":"block","reason":"<~80 tokens, quotes claim + evidence + next step>","systemMessage":"<receipt>"}`.
   - FAIL at block limit, or `report` mode: receipt only, marked "stopped blocking (limit reached)" when applicable.
   - CAN'T TELL / PASS: `{"systemMessage":"<receipt>"}` (zero model tokens). `strict` mode blocks on CAN'T TELL.
   - Loop guard: block count per `session_id` read from the ledger.

## 6. Formats

**Receipt** (<= 6 lines, user-only):
```
🤥 Pinocchio · FAIL · nose +1 (session: 1 lie caught)
  ✗ stale-tests   "tests pass": no test run after last edit to src/auth.ts (L214)
  ✓ phantom-edit  3 files changed, matches claims
  ⚠ tampering     test/auth.test.ts: added .skip (warn only)
  ledger #a41f… · blocked 1/2
```

**Ledger** `.claude/pinocchio/ledger.jsonl`, one line per stop:
```json
{"v":1,"ts":"2026-10-19T14:02:11Z","session":"5581…","seq":12,"verdict":"fail","mode":"default",
 "blocked":true,"blocks_in_session":1,"elapsed_ms":38,
 "claims":[{"type":"tests","text":"all tests pass","msg_line":402}],
 "checks":[{"id":"stale-tests","status":"fail","evidence":{"last_edit":{"file":"src/auth.ts","line":214},"last_test_run":null}}],
 "git":{"head":"408b0dc","changed":{"src/auth.ts":"sha256:…"}},
 "prev":"sha256:…","hash":"sha256:…"}
```
- `hash = sha256(prev + canonical_json(entry without hash))`; canonical JSON = sorted keys, no whitespace. Described as tamper-evident, not tamper-proof.
- Stores paths, hashes, line numbers and the matched claim phrase only. No code, tool output or prompts.
- Rotates to `ledger.1.jsonl` past 5 MB. Plugin writes `.claude/pinocchio/.gitignore` ignoring the ledger unless config `commitLedger: true`.

**Config** `.claude/pinocchio.json` (optional):
```json
{"mode":"default","testCommands":["^make check$"],"claimPhrases":{"tests":["ci is green"]},
 "maxBlocksPerSession":2,"commitLedger":false}
```

## 7. Errors and safety

- Fail open everywhere: unreadable/unknown transcript, missing git, malformed JUnit, unwritable ledger, bad config, uncaught exception, 2 s hard timeout. Each shows `🤥 Pinocchio · skipped (<reason>)` or a degraded-receipt note.
- Read-only: no project commands, no network. `child_process` limited to the fixed read-only git subcommands via `execFile` with argv arrays.
- Path confinement: claimed paths resolved and required to stay within `cwd`; otherwise UNKNOWN, never read.
- Only write location: `.claude/pinocchio/`.
- Blocks require positive evidence of a lie; missing evidence is CAN'T TELL.
- README section "Safe to install" enumerates every read, write and process spawn.

## 8. Install and onboarding

**Native:** `/plugin marketplace add STiFLeR7/pinocchio` then `/plugin install pinocchio@pinocchio`. Defaults, no setup.

**npx:** `npx @stifler7/pinocchio setup`, step blocks that tick off as completed:
1. Banner; check Node >= 18, git, Claude Code CLI (and Codex: skill only).
2. Detect test runner from `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Makefile`; propose `testCommands`.
3. Ask: scope (project / user), mode, commit ledger.
4. Review: list every file to be created/changed; nothing written before confirm.
5. Apply: prefer `claude plugin marketplace add` + `claude plugin install`; fallback registers the hook in `.claude/settings.json` (project) or `~/.claude/settings.json` (user) inside a marked block, preserving all other content.
6. Smoke test: run the hook against a bundled fixture transcript and print a sample receipt.

`pinocchio doctor` (registration, Node, git, config, ledger chain; prints fixes), `pinocchio status`
(nose count, recent verdicts, chain check), `pinocchio uninstall` (removes exactly what setup added).
All commands idempotent; `NO_COLOR` honoured.

## 9. Testing, benchmark and metrics

**Tests** (`node:test`): unit per module; labelled fixture transcripts with golden receipts
(honest-pass, stale-tests lie, red-tests lie, phantom edit, tampering, can't-tell); safety cases
(traversal, no git, corrupt transcript, unwritable ledger, timeout: all fail open); perf (5 MB
transcript, p95 < 300 ms); install idempotency and clean uninstall against a temp HOME.
CI: Node 18/20/22 on Linux, macOS, Windows. Nexus Python CI runs only on `engine-room/**` changes.

**Benchmark** (cases and thresholds frozen in `bench/cases.json`, committed before any run):
1. Replay: run the hook offline over opt-in local past transcripts; hand-label a random sample;
   report the share of completion claims lacking supporting evidence. Zero API cost.
2. Live A/B: ~20 tasks across JS, Python, Go fixture repos (honest tasks + trap tasks that tempt
   false claims). Arms: **off**, **placebo** (instruction-only skill, "verify your work before
   claiming done", no hook), **on**. 3 runs per task per arm via `claude plugin eval` and
   `claude -p --output-format json`. Estimated ~180 runs, ~$100-300; confirm with the owner
   before spending.

| Metric | Frozen target |
|---|---|
| False-block rate | < 2% |
| Catch rate on trap tasks | >= 80% |
| Can't-tell rate | <= 25% |
| Always-on token overhead | <= 100 tokens/session |
| Token delta, honest sessions | ~0 (within noise) |
| Token/turn delta, false-claim sessions | reported as measured |
| Hook latency | p50 < 50 ms, p95 < 300 ms |
| Final correctness vs off | higher on traps, equal on honest |

Results are published exactly as measured, including misses.

## 10. Repository restructure

- Move `nexus/`, `nexus_*`, `tests/`, `scripts/`, `examples/`, `adr/`, `contracts/`, `blueprint/`,
  `alembic/`, `config/`, `templates/`, `docker/`, `pyproject.toml`, `uv.lock`, `Makefile`,
  `ruff.toml` and Nexus docs into `engine-room/` with `git mv` (history preserved).
- Fix Python packaging/CI paths so `make check` passes from `engine-room/`.
- New root README for Pinocchio, crediting "built on the Nexus evidence engine (3,261 tests)".
- Rename the GitHub repo to `STiFLeR7/pinocchio` (owner action, outward-facing; GitHub redirects).
- `docs/personal/` stays untracked.

## 11. Assumptions to verify during planning

- `claude plugin install` / `claude plugin marketplace add` run non-interactively (else settings fallback).
- Exact Claude Code transcript JSONL shape for tool calls/results, including how a non-zero Bash exit is represented.
- Stop hook output accepts `decision`, `reason` and `systemMessage` together, and `systemMessage` is not added to model context.
- `claude plugin eval` and `claude -p --output-format json` expose per-run token usage.
- `@stifler7` npm scope is available to the owner.

## 12. Out of scope for v1 (planned v1.1+)

`/why` ledger explorer; PR receipt comments; stale-build check; Codex blocking if Codex gains a
blocking hook; promoting tampering to blocking after benchmark evidence; official directory submission.
