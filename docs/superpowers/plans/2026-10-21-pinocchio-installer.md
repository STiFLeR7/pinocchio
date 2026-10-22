# Pinocchio Installer (npx CLI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `npx @stifler7/pinocchio setup | doctor | status | uninstall` — a zero-dependency onboarding CLI with step blocks that installs, checks, reports on and cleanly removes Pinocchio.

**Architecture:** A `bin/pinocchio.js` entry dispatches to small modules under `cli/`: a UI kit that renders the approved banner and step boxes, detectors (system tools, test runners), a thin adapter over the `claude plugin` CLI, an install-state file that records exactly what setup added, and one module per command. The CLI only reads Pinocchio's runtime (`src/config.js`, `src/ledger.js`, `src/stop.js`) and never changes it.

**Tech Stack:** Node.js >= 18 stdlib only (`readline`, `child_process`, `fs`, `node:test`).

**Spec:** `docs/superpowers/specs/2026-10-19-pinocchio-design.md` §8; approved screens: `docs/superpowers/specs/2026-10-21-onboarding-screens.md`.

## Global Constraints

- Zero runtime dependencies; Node >= 18; Linux, macOS, Windows.
- Do not modify `src/`, `hooks/`, `skills/` or `.claude-plugin/` (a benchmark runs against them); import from `src/` read-only.
- Nothing is written before the Review step is confirmed. All commands are idempotent. `NO_COLOR` is honoured.
- Setup steps, in order: 1 Check system, 2 Find tests, 3 Choose, 4 Review, 5 Install, 6 Test — rendered as in the approved screens (✔ done green, ◉ running yellow, ○ waiting, ✖ failed red; ASCII `+--+` boxes when box glyphs are unavailable).
- Apply prefers `claude plugin marketplace add STiFLeR7/pinocchio --scope <scope> --json` then `claude plugin install pinocchio@pinocchio --scope <scope> -y --json`; fallback (no `claude` CLI, or the CLI fails) registers the Stop hook in `.claude/settings.json` (project) or `~/.claude/settings.json` (user), preserving every other key.
- `uninstall` removes exactly what setup added (per the install-state file) and nothing else; the ledger is user data and is kept.
- Config lives at `<project>/.claude/pinocchio.json`: `{ "mode": "default"|"report"|"strict", "testCommands": [regex strings], "commitLedger": boolean }`.
- Codex: detected and reported only ("skill only — Codex has no blocking hook"); setup installs nothing for Codex.

## Review Focus

- Existing `settings.json` with comments, trailing commas or other invalid JSON: the fallback must refuse to touch it and print the manual snippet, never overwrite. Test in Task 4.
- Non-TTY / CI (`npx ... setup` piped): no prompt hangs — without `--yes` it prints the review and exits 1 with `re-run with --yes`; with `--yes` it uses flags or defaults. Test in Task 4.
- Running setup twice: second run reports every step as already done and writes nothing new. Test in Task 4.
- `claude` CLI present but `marketplace add` fails (offline, GitHub down): fall back to settings hook, and say why. Test in Task 4.
- Uninstall after the user edited `.claude/pinocchio.json`: keep the edited file and say so (only remove files whose hash still matches what setup wrote). Test in Task 6.

---

### Task 1: UI kit

**Files:** Create `cli/ui.js`; Test `test/cli-ui.test.js`.

**Interfaces — Produces:**
- `createUI({ color = !process.env.NO_COLOR && stream.isTTY, unicode = supportsUnicode(), stream = process.stdout, width = 64 }) -> ui` with methods `banner(version: string)`, `progress(steps: {n, label, state: 'done'|'running'|'waiting'|'failed'}[])`, `box(title: string, state, lines: string[])`, `line(text)`, and a `render*` twin of each returning the string (for tests).
- `supportsUnicode(env = process.env, platform = process.platform) -> boolean`: true off Windows; on Windows true if `WT_SESSION`, `TERM_PROGRAM`, or `ConEmuANSI=ON` is set; `PINOCCHIO_ASCII=1` forces false.
- Banner text exactly as the approved screens (the PINOCCHIO block letters plus `🤥  Your agent's nose grows when it lies.   v<version>`); ASCII mode prints `PINOCCHIO v<version> — Your agent's nose grows when it lies.` instead.

- [ ] **Step 1: Failing tests:** `box renders title, state glyph and padded lines` (unicode: starts with `╭─ ✔ Step 1 · Check system`, every line same visible width, ends `╰…╯`); `ascii box uses +- and |` ; `NO_COLOR strips ANSI` (no `\x1b[` in output when color false); `progress strip shows six steps with glyphs` (`✔ 1  Check system`, `◉ 2  Find tests`, `○ 3  Choose`); `supportsUnicode false on plain win32, true with WT_SESSION, false with PINOCCHIO_ASCII=1`; `long lines are clipped to width with …`.
- [ ] **Step 2:** `node --test test/cli-ui.test.js` — FAIL (module missing).
- [ ] **Step 3:** Implement. Visible width ignores ANSI codes; emoji count as width 2.
- [ ] **Step 4:** `npm test` — PASS.
- [ ] **Step 5:** Commit `feat(cli): step-block UI kit`.

### Task 2: Detectors

**Files:** Create `cli/detect.js`; Test `test/cli-detect.test.js`.

**Interfaces — Produces:**
- `checkSystem({ run = spawnVersion } = {}) -> { node: {ok, version}, git: {ok, version}, claude: {ok, version}, codex: {ok, version} }` where `node.ok = major >= 18`; `run(cmd) -> string|null` runs `<cmd> --version` (shell on win32 for `.cmd` shims), 3 s timeout.
- `detectTests(dir) -> { file, command, regex }[]` in this order: `package.json` with `scripts.test` not the npm default (`echo "Error: no test specified" && exit 1`) → `npm test` / `^npm (run )?test\b`; `pyproject.toml` containing `pytest` or `[tool.pytest` → `pytest` / `\bpytest\b`; `go.mod` → `go test ./...` / `^go test\b`; `Cargo.toml` → `cargo test` / `^cargo test\b`; `Makefile` with a `test:` target → `make test` / `^make test\b`. Missing files are reported by the UI as `─ <file> → not found` (Task 4), not here.

- [ ] **Step 1: Failing tests:** `node below 18 is not ok` (stub run returns `v16.20.0`); `missing claude gives ok:false`; `detects npm, pytest, go, cargo, make in one dir` (temp dir with all five; commands and regexes as above); `default npm test script is ignored`; `empty dir gives []`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** `npm test` PASS. **Step 5:** Commit `feat(cli): system and test-runner detection`.

### Task 3: Claude adapter and install state

**Files:** Create `cli/claude.js`, `cli/state.js`; Create `test/fixtures/stub-claude-cli.mjs`; Test `test/cli-claude.test.js`.

**Interfaces — Produces:**
- `claudeCli({ bin = process.env.PINOCCHIO_CLAUDE || 'claude' }) -> { marketplaceAdd(scope), install(scope), uninstall(scope), marketplaceRemove(scope), listPlugins() }`; each returns `{ ok: boolean, json: object|null, stderr: string }` from running the `claude plugin …` commands with `--json` (exact argv: `plugin marketplace add STiFLeR7/pinocchio --scope <s> --json`; `plugin install pinocchio@pinocchio --scope <s> -y --json`; `plugin uninstall pinocchio@pinocchio --scope <s> --json`; `plugin marketplace remove pinocchio --scope <s> --json`; `plugin list --json`). When `bin` ends in `.mjs`/`.js` it is run with `process.execPath` (test seam). 60 s timeout.
- `statePath(scope, projectDir, home = os.homedir()) -> string`: project → `<projectDir>/.claude/pinocchio/install.json`; user → `<home>/.claude/pinocchio/install.json`.
- `readState(file) -> State|null`, `writeState(file, State)`; `State = { version: 1, scope, method: 'plugin'|'settings', addedMarketplace: boolean, files: [{ path, sha256 }], settings: { file, hookCommand } | null, at: ISO }`.
- `sha256File(path) -> string|null`.

- [ ] **Step 1: Failing tests** with the stub (records argv to a log file given by `STUB_LOG`, exits per `STUB_FAIL=<subcommand>`): `install runs the exact argv with -y and --json`; `failure surfaces ok:false and stderr`; `statePath for both scopes`; `state round-trips`; `.js bin runs through node`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit `feat(cli): claude plugin adapter and install state`.

### Task 4: `setup`

**Files:** Create `cli/prompt.js`, `cli/setup.js`, `cli/fallback.js`, `cli/smoke.js`; Test `test/cli-setup.test.js`.

**Interfaces — Consumes:** Tasks 1–3; `loadConfig` from `src/config.js`; `run` from `src/stop.js`.
**Produces:**
- `select(question, options: {label, value}[], { input, output, defaultIndex = 0 }) -> Promise<value>` (arrow keys + Enter on a TTY; numbered list + typed number otherwise).
- `setup({ cwd, home, argv, ui, prompt, cli, isTTY }) -> Promise<0|1>`; flags: `--yes`, `--scope project|user`, `--mode default|report|strict`, `--commit-ledger`.
- `registerHook(settingsFile, command) -> { ok, reason? }` and `unregisterHook(settingsFile, command) -> boolean` in `fallback.js`: parse JSON; on parse failure return `{ ok:false, reason:'settings.json is not plain JSON' }` and never write; add `{ hooks: [{ type: 'command', command, timeout: 5 }] }` under `hooks.Stop` unless an identical command exists; preserve all other keys and order; write with 2-space indent.
- Fallback runtime: copy the package's `src/` and `package.json` to `<scopeRoot>/.claude/pinocchio/runtime/` and use `node "<that dir>/src/stop.js"` as the hook command (the npx cache is temporary).
- `smokeTest() -> { ok, receipt }` in `smoke.js`: in a temp git repo, a transcript with one edit and the claim `All tests pass.` and no test run; `run()` with `CLAUDE_PROJECT_DIR` = a temp dir; returns the `systemMessage` (expected to start `🤥 Pinocchio · FAIL`).

Flow: Step 1 renders checkSystem (Node < 18 or no git → ✖ and exit 1 with the fix line). Step 2 renders detectTests for cwd (each found file `✔ <file> → <command>`, the others `─ <file> → not found`). Step 3 asks scope (default project), mode (default), commit ledger (default no) — or takes flags. Step 4 lists every file/registration to be created and `Token cost: ~93 tokens/session · 0 for the hook itself` and `Reads only: never edits code, never runs commands for you`; asks `Install now?` (non-TTY without `--yes`: print and exit 1 with `re-run with --yes`). Step 5: plugin path, else fallback with the reason shown; write `.claude/pinocchio.json` only if absent (else ✔ kept existing); write install state. Step 6: smoke test receipt. Finish with the `🎉  Pinocchio is watching.` block and the three follow-up commands. If install state already exists and the plugin/hook is present, every step shows ✔ `already set up` and nothing is written.

- [ ] **Step 1: Failing tests** (temp project dir, temp HOME via `home` param, stub claude CLI, `ui` with color off, scripted `prompt`): `--yes project install calls marketplace add + install with --scope project and writes config + state`; `nothing is written when the user answers No at Review` (dir listing unchanged); `non-TTY without --yes exits 1 and writes nothing`; `second run is a no-op showing already set up`; `marketplace add failure falls back to settings hook with runtime copy and says why`; `invalid settings.json is never written; prints manual snippet; exit 1`; `existing pinocchio.json is kept`; `Node 16 stops at step 1`; `smoke test receipt starts with 🤥 Pinocchio · FAIL`; `user scope writes state under HOME`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** `npm test` PASS. **Step 5:** Commit `feat(cli): setup with step blocks, review gate and fallback`.

### Task 5: `doctor` and `status`

**Files:** Create `cli/doctor.js`, `cli/status.js`; Test `test/cli-doctor-status.test.js`.

**Interfaces — Consumes:** Tasks 1–3; `loadConfig`, `readEntries`, `verifyChain` from `src/`.
**Produces:** `doctor({ cwd, home, ui, cli }) -> 0|1` — checks: Node >= 18; git; registration (`cli.listPlugins()` contains `pinocchio`, or the state's settings hook command is present in the settings file); config (`loadConfig(cwd).notes` empty); ledger chain (`verifyChain(cwd)` ok or no ledger yet). Each failed check prints one fix line (e.g. `run: npx @stifler7/pinocchio setup`). Exit 1 if any check failed.
`status({ cwd, ui }) -> 0` — renders the approved status box: nose length bar (10 cells, `▇` filled = min(10, fails)), `N lies caught`, `Sessions  S checked · P pass · F fail · C can't tell` (by distinct `session`, verdict of each session's last entry), `Last 3` verdicts with the first failing check id, `Ledger ✔ hash chain intact (E entries)` or `✖ chain broken at entry K`. No ledger → `No sessions yet — Pinocchio writes a receipt after your agent's next edit.`

- [ ] **Step 1: Failing tests:** `doctor all green exits 0`; `doctor with bad config JSON exits 1 and names the fix`; `doctor with broken chain reports it`; `status counts sessions by last verdict` (synthetic ledger via `appendEntry`); `status with no ledger prints the empty message`; `status chain broken line`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit `feat(cli): doctor and status`.

### Task 6: `uninstall`, bin entry and package wiring

**Files:** Create `cli/uninstall.js`, `bin/pinocchio.js`; Modify `package.json` (`"bin": { "pinocchio": "bin/pinocchio.js" }`, add `"bin"` and `"cli"` to `files`); Test `test/cli-uninstall.test.js`, `test/cli-bin.test.js`.

**Interfaces — Produces:** `uninstall({ cwd, home, argv, ui, cli }) -> 0|1` — reads state (project, then user unless `--scope`); plugin method → `cli.uninstall(scope)` and `cli.marketplaceRemove(scope)` only if `addedMarketplace`; settings method → `unregisterHook`; deletes each recorded file only if its sha256 still matches (else ✔ `kept <file> (changed since setup)`); deletes the runtime copy; deletes the state file; keeps the ledger (`ledger kept at .claude/pinocchio/`). No state → `Nothing to remove — Pinocchio was not installed by setup here.` exit 0.
`bin/pinocchio.js`: `#!/usr/bin/env node`; `pinocchio <setup|doctor|status|uninstall> [flags]`, `--help`, `--version` (from package.json); unknown command → usage + exit 1. Default command with no args = `setup`.

- [ ] **Step 1: Failing tests:** `uninstall after plugin setup calls uninstall + marketplace remove and deletes config and state`; `edited config is kept`; `settings fallback hook removed, other keys intact`; `no state prints nothing to remove`; `uninstall twice is a no-op`; `bin --version prints package version`; `bin unknown command exits 1`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** `npm test` and `npm pack --dry-run` (lists bin/, cli/, src/, hooks/, skills/, .claude-plugin/; no bench/ or test/). **Step 5:** Commit `feat(cli): uninstall and npx entry`.
