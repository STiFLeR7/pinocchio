# Pinocchio Core Plugin Implementation Plan (Plan 1 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the repo so Nexus lives in `engine-room/`, then build the Pinocchio Claude Code plugin (Stop hook + skill) that checks completion claims against transcript, filesystem and git evidence, installable natively with `/plugin`.

**Architecture:** A zero-dependency Node.js (ESM) Stop hook. `src/stop.js` is the only stdin/stdout module; it parses the transcript into events, matches claims, runs four pure check functions, decides a verdict, appends a hash-chained ledger line and prints Claude Code hook JSON. Everything fails open.

**Tech Stack:** Node.js >= 18 (ESM, `node:test`, `node:fs`, `node:crypto`, `node:child_process`), git CLI (read-only), Claude Code plugin format. Nexus stays Python/uv inside `engine-room/`.

**Spec:** `docs/superpowers/specs/2026-10-19-pinocchio-design.md`

**Out of this plan:** `npx` onboarding CLI (Plan 2), benchmark harness and launch README (Plan 3).

## Global Constraints

- Node.js >= 18; zero runtime and dev dependencies; ESM (`"type": "module"`).
- Read-only: never run project commands; no network; `child_process` only via `execFileSync('git', [...])` with subcommands `rev-parse`, `status`, `diff`, `log`.
- Only write location: `<project root>/.claude/pinocchio/ (project root = CLAUDE_PROJECT_DIR, else the git root, else cwd)`.
- Fail open: any internal error yields no block; at most a `🤥 Pinocchio · skipped (<reason>)` systemMessage.
- Block only on FAIL (default mode); `report` never blocks; `strict` also blocks CAN'T TELL; max 2 blocks per session by default.
- Receipt <= 6 lines; delivered via `systemMessage` (user-only). Block `reason` quotes claim + evidence.
- Ledger stores paths, hashes, line numbers, matched claim phrases only; never code, tool output or prompts.
- npm package name `@stifler7/pinocchio`; plugin name `pinocchio`; repo `STiFLeR7/pinocchio`.
- Commit messages: Conventional Commits, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Tests: `node --test` from the repo root; test files are `test/**/*.test.js`.

## Review Focus

1. A Bash test command that was **denied by permissions or rejected by the user** (`is_error: true` without `Exit code N`) never ran: it must count as neither a failed nor a completed test run. (Task 3)
2. **Path spelling differences**: edit events carry absolute paths (Windows drive letters, backslashes) while git reports root-relative forward-slash paths; the same file must match. (Tasks 4, 8)
3. **Negated claims** such as "tests don't pass yet" or "I haven't run the tests" must not register as a tests claim. (Task 5)
4. **Garbage or partially written transcript lines** (the transcript is appended live) must be skipped without crashing. (Task 3)
5. **cwd is a subdirectory of the git repo**: git paths are relative to the repo root, not cwd; phantom-edit must still match. (Task 8)

---

## File Structure

```
.claude-plugin/plugin.json        plugin manifest
.claude-plugin/marketplace.json   single-plugin marketplace
hooks/hooks.json                  Stop hook registration
skills/pinocchio/SKILL.md         skill (short description, usage body)
package.json                      @stifler7/pinocchio, type module, node --test
src/stop.js                       entry + run(input, deps) orchestration (only I/O module besides git/ledger/config)
src/config.js                     loadConfig(cwd)
src/transcript.js                 parseTranscript(text)
src/paths.js                      norm, confine, rel
src/claims.js                     matchClaims(text, config)
src/testcmd.js                    isTestCommand, looksLikeTest, repoHasTestSetup
src/git.js                        readGitState, testFileDiff, committedSince, hashFile
src/junit.js                      parseJUnit, findFreshJUnit
src/checks/util.js                afterLastEdit, shortCmd
src/checks/stale-tests.js         staleTests(ctx)
src/checks/red-tests.js           redTests(ctx)
src/checks/phantom-edit.js        phantomEdit(ctx)
src/checks/tampering.js           tampering(ctx)
src/verdict.js                    decide(results, claims)
src/receipt.js                    formatReceipt(opts), formatReason(results)
src/ledger.js                     canonical, appendEntry, readEntries, sessionStats, verifyChain
test/helpers.js                   transcript builders, temp dirs, temp git repos
test/*.test.js                    one suite per module + stop integration + perf
.github/workflows/plugin-ci.yml   Node 18/20/22 x ubuntu/macos/windows
engine-room/                      Nexus v1 + v2, moved with git mv
```

---

### Task 1: Move Nexus into `engine-room/`

**Files:**
- Move (git mv): everything tracked at the root except `.github/`, `.gitignore`, `.gitattributes`, `LICENSE`, `SECURITY.md`, `docs/superpowers/`
- Modify: `.github/workflows/core-ci.yml`, `.github/workflows/ci.yml`, `.gitignore`
- Create: `README.md` (interim)

**Interfaces:**
- Consumes: nothing.
- Produces: `engine-room/` containing the full Nexus project; root free for the plugin.

- [ ] **Step 1: Record the baseline test count before moving**

Run: `uv run pytest -q -p no:cacheprovider 2>&1 | tail -3`
Expected: a final line like `3261 passed` (note the exact number for Step 6).

- [ ] **Step 2: Move tracked top-level items**

```bash
mkdir -p engine-room/docs
for item in $(git ls-files | cut -d/ -f1 | sort -u); do
  case "$item" in
    .github|.gitignore|.gitattributes|LICENSE|SECURITY.md|docs) ;;
    *) git mv "$item" "engine-room/$item" ;;
  esac
done
for d in docs/*; do
  case "$d" in
    docs/superpowers|docs/personal) ;;
    *) git ls-files --error-unmatch "$d" >/dev/null 2>&1 && git mv "$d" engine-room/docs/ ;;
  esac
done
git status --short | head
```
Expected: only `R` (rename) entries; `docs/superpowers/` and untracked `docs/personal/` stay at the root.

- [ ] **Step 3: Point the Python CI at `engine-room/`**

In both `.github/workflows/core-ci.yml` and `.github/workflows/ci.yml`, add a top-level `defaults` block and a path filter under each trigger. Example for `core-ci.yml` (keep the existing `on:` branches; add `paths`):

```yaml
on:
  push:
    branches: [master]
    paths: ['engine-room/**', '.github/workflows/core-ci.yml']
  pull_request:
    paths: ['engine-room/**', '.github/workflows/core-ci.yml']

defaults:
  run:
    working-directory: engine-room
```

Then fix any remaining root-relative paths in those files:

Run: `grep -nE "uv.lock|pyproject.toml|coverage.xml|cache-dependency-glob" .github/workflows/*.yml`
For each hit, prefix the path with `engine-room/` (for example `cache-dependency-glob: engine-room/uv.lock`, `files: engine-room/coverage.xml`).

- [ ] **Step 4: Unanchor root-anchored ignore patterns**

Run: `grep -nE "^/" .gitignore`
For each pattern starting with `/` that names a Nexus artifact (for example `/data/`, `/dist/`, `/coverage.xml`), add a duplicate line with the `engine-room` prefix, e.g. `/engine-room/data/`. Leave unanchored patterns (`.venv/`, `__pycache__/`) as they are.

- [ ] **Step 5: Write the interim root README**

`README.md`:
```markdown
# 🤥 Pinocchio

> Your agent's nose grows when it lies.

A Claude Code plugin that checks your agent's "done" and "tests pass" claims against evidence it
didn't produce itself. Under construction; launch README coming soon.

**Engine room:** Pinocchio is built on the Nexus evidence engine. Nexus v1 and v2 live, unchanged,
in [`engine-room/`](engine-room/README.md).
```

- [ ] **Step 6: Verify Nexus still passes from its new home**

Run: `cd engine-room && uv sync --frozen && uv run pytest -q -p no:cacheprovider 2>&1 | tail -3; cd ..`
Expected: the same pass count as Step 1, 0 failed.

- [ ] **Step 7: Commit**

```bash
git add -A .gitignore README.md .github engine-room
git commit -m "refactor: move Nexus into engine-room/ to make room for Pinocchio

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Plugin scaffold, test helpers and config loader

**Files:**
- Create: `package.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `hooks/hooks.json`, `.github/workflows/plugin-ci.yml`, `src/config.js`, `test/helpers.js`, `test/config.test.js`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `loadConfig(cwd: string) -> Config` where `Config = { mode: 'default'|'report'|'strict'|'off', testCommands: RegExp[], claimPhrases: { tests: string[], fixed: string[] }, maxBlocksPerSession: number, commitLedger: boolean, notes: string[] }`
  - `test/helpers.js`: `tmpdir()`, `initRepo(dir)`, `gitIn(dir, ...args)`, `assistantText(text, ts?)`, `bash(cmd, {exit, stdout, ts}?)`, `edit(file, ts?)`, `denied(cmd)`, `jsonl(...items)`

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "@stifler7/pinocchio",
  "version": "0.1.0",
  "description": "Your agent's nose grows when it lies. Checks AI coding agent completion claims against evidence.",
  "type": "module",
  "license": "MIT",
  "engines": { "node": ">=18" },
  "repository": { "type": "git", "url": "git+https://github.com/STiFLeR7/pinocchio.git" },
  "files": ["src", "hooks", "skills", ".claude-plugin"],
  "scripts": { "test": "node --test" }
}
```

- [ ] **Step 2: Create plugin manifest, marketplace and hook registration**

`.claude-plugin/plugin.json`:
```json
{
  "name": "pinocchio",
  "version": "0.1.0",
  "description": "Your agent's nose grows when it lies. Checks 'done' and 'tests pass' claims against evidence the agent didn't produce.",
  "author": { "name": "STiFLeR7", "url": "https://github.com/STiFLeR7" },
  "hooks": "./hooks/hooks.json"
}
```

`.claude-plugin/marketplace.json`:
```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "pinocchio",
  "description": "Catch your AI agent's false 'done' claims.",
  "owner": { "name": "STiFLeR7", "url": "https://github.com/STiFLeR7" },
  "plugins": [
    { "name": "pinocchio", "description": "Checks completion claims against transcript, test and git evidence.", "source": "./", "category": "productivity" }
  ]
}
```

`hooks/hooks.json`:
```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node \"${CLAUDE_PLUGIN_ROOT}/src/stop.js\"",
            "commandWindows": "if (Get-Command node -ErrorAction SilentlyContinue) { node \"$env:CLAUDE_PLUGIN_ROOT\\src\\stop.js\" }",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 3: Create the Node CI workflow**

`.github/workflows/plugin-ci.yml`:
```yaml
name: plugin-ci
on:
  push:
    branches: [master]
    paths-ignore: ['engine-room/**']
  pull_request:
    paths-ignore: ['engine-room/**']
jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        node: [18, 20, 22]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '${{ matrix.node }}' }
      - run: git config --global user.email ci@example.com && git config --global user.name ci
      - run: npm test
```

- [ ] **Step 4: Write test helpers**

`test/helpers.js`:
```js
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

let n = 0;
const T0 = Date.parse('2026-10-19T10:00:00Z');
const stamp = (ts) => new Date(ts ?? T0 + (++n) * 1000).toISOString();

export function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'pino-'));
}

export function gitIn(dir, ...args) {
  return execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...args], {
    cwd: dir, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'],
  });
}

export function initRepo(dir) {
  gitIn(dir, 'init', '-q');
  fs.writeFileSync(path.join(dir, 'README.md'), 'x\n');
  gitIn(dir, 'add', '.');
  gitIn(dir, 'commit', '-q', '-m', 'init');
  return dir;
}

export function assistantText(text, ts) {
  return { type: 'assistant', timestamp: stamp(ts), message: { role: 'assistant', content: [{ type: 'text', text }] } };
}

function toolUse(name, input, ts) {
  const id = `toolu_${++n}`;
  return [id, { type: 'assistant', timestamp: stamp(ts), message: { role: 'assistant', content: [{ type: 'tool_use', id, name, input }] } }];
}

function toolResult(id, { isError = false, text = '', stdout = null, stderr = '' } = {}) {
  const o = { type: 'user', timestamp: stamp(), message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: id, is_error: isError, content: text }] } };
  if (stdout !== null) o.toolUseResult = { stdout, stderr, interrupted: false };
  return o;
}

export function bash(cmd, { exit = 0, stdout = '', ts } = {}) {
  const [id, use] = toolUse('Bash', { command: cmd }, ts);
  const res = exit === 0
    ? toolResult(id, { stdout })
    : toolResult(id, { isError: true, text: `Exit code ${exit}\n${stdout}` });
  return [use, res];
}

export function denied(cmd) {
  const [id, use] = toolUse('Bash', { command: cmd });
  return [use, toolResult(id, { isError: true, text: 'Permission for this action was denied.' })];
}

export function edit(file, ts) {
  const [id, use] = toolUse('Edit', { file_path: file, old_string: 'a', new_string: 'b' }, ts);
  return [use, toolResult(id, { text: 'The file has been updated.' })];
}

export function jsonl(...items) {
  return items.flat(2).map((o) => (typeof o === 'string' ? o : JSON.stringify(o))).join('\n') + '\n';
}
```

- [ ] **Step 5: Write the failing config tests**

`test/config.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { loadConfig } from '../src/config.js';
import { tmpdir } from './helpers.js';

function withConfig(obj) {
  const dir = tmpdir();
  fs.mkdirSync(path.join(dir, '.claude'));
  fs.writeFileSync(path.join(dir, '.claude', 'pinocchio.json'), typeof obj === 'string' ? obj : JSON.stringify(obj));
  return dir;
}

test('defaults when no config file', () => {
  const c = loadConfig(tmpdir());
  assert.equal(c.mode, 'default');
  assert.equal(c.maxBlocksPerSession, 2);
  assert.equal(c.commitLedger, false);
  assert.deepEqual(c.testCommands, []);
  assert.deepEqual(c.notes, []);
});

test('reads valid fields', () => {
  const c = loadConfig(withConfig({ mode: 'strict', testCommands: ['^make verify$'], claimPhrases: { tests: ['CI Is Green'] }, maxBlocksPerSession: 1, commitLedger: true }));
  assert.equal(c.mode, 'strict');
  assert.ok(c.testCommands[0].test('make verify'));
  assert.deepEqual(c.claimPhrases.tests, ['ci is green']);
  assert.equal(c.maxBlocksPerSession, 1);
  assert.equal(c.commitLedger, true);
});

test('invalid JSON falls back to defaults with a note', () => {
  const c = loadConfig(withConfig('{not json'));
  assert.equal(c.mode, 'default');
  assert.deepEqual(c.notes, ['config ignored: invalid JSON']);
});

test('unknown mode and bad regex are noted, not fatal', () => {
  const c = loadConfig(withConfig({ mode: 'yolo', testCommands: ['(unclosed'] }));
  assert.equal(c.mode, 'default');
  assert.equal(c.testCommands.length, 0);
  assert.equal(c.notes.length, 2);
});
```

- [ ] **Step 6: Run to verify failure**

Run: `node --test test/config.test.js`
Expected: FAIL with `Cannot find module` for `src/config.js`.

- [ ] **Step 7: Implement `src/config.js`**

```js
import fs from 'node:fs';
import path from 'node:path';

const MODES = new Set(['default', 'report', 'strict', 'off']);

function defaults() {
  return { mode: 'default', testCommands: [], claimPhrases: { tests: [], fixed: [] }, maxBlocksPerSession: 2, commitLedger: false, notes: [] };
}

export function loadConfig(cwd) {
  const cfg = defaults();
  let raw;
  try {
    raw = fs.readFileSync(path.join(cwd, '.claude', 'pinocchio.json'), 'utf8');
  } catch {
    return cfg;
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    cfg.notes.push('config ignored: invalid JSON');
    return cfg;
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    cfg.notes.push('config ignored: not an object');
    return cfg;
  }
  if (parsed.mode !== undefined) {
    if (MODES.has(parsed.mode)) cfg.mode = parsed.mode;
    else cfg.notes.push(`config: unknown mode "${parsed.mode}", using default`);
  }
  if (Array.isArray(parsed.testCommands)) {
    for (const s of parsed.testCommands) {
      try {
        cfg.testCommands.push(new RegExp(s));
      } catch {
        cfg.notes.push(`config: bad testCommands regex "${s}"`);
      }
    }
  }
  for (const k of ['tests', 'fixed']) {
    const v = parsed.claimPhrases?.[k];
    if (Array.isArray(v)) cfg.claimPhrases[k] = v.filter((x) => typeof x === 'string' && x.trim()).map((x) => x.toLowerCase());
  }
  if (Number.isInteger(parsed.maxBlocksPerSession) && parsed.maxBlocksPerSession >= 0) cfg.maxBlocksPerSession = parsed.maxBlocksPerSession;
  if (typeof parsed.commitLedger === 'boolean') cfg.commitLedger = parsed.commitLedger;
  return cfg;
}
```

- [ ] **Step 8: Run tests and validate the plugin manifest**

Run: `node --test test/config.test.js && claude plugin validate .`
Expected: 4 tests PASS; validate reports the plugin and marketplace as valid (if it reports the missing `src/stop.js`, that is expected until Task 12; any schema error must be fixed now).

- [ ] **Step 9: Commit**

```bash
git add package.json .claude-plugin hooks .github/workflows/plugin-ci.yml src/config.js test/helpers.js test/config.test.js
git commit -m "feat: scaffold Pinocchio plugin and config loader

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Transcript parser

**Files:**
- Create: `src/transcript.js`, `test/transcript.test.js`

**Interfaces:**
- Consumes: transcript JSONL text.
- Produces: `parseTranscript(text: string) -> { events: Event[], lastAssistantText: string|null, startTs: number }` where
  - `Event = { kind: 'edit', file: string, line: number, ts: number } | { kind: 'bash', cmd: string, failed: boolean, exitCode: number, output: string, line: number, ts: number }`
  - `line` is the 1-based transcript line of the tool_use; events sorted by `line`; `startTs` is the first parseable timestamp in ms (NaN if none).

- [ ] **Step 1: Write the failing tests**

`test/transcript.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseTranscript } from '../src/transcript.js';
import { jsonl, bash, edit, denied, assistantText } from './helpers.js';

test('parses edits and bash results in order', () => {
  const t = jsonl(edit('/repo/src/a.js'), bash('npm test', { stdout: '5 passing' }), assistantText('All tests pass.'));
  const { events, lastAssistantText } = parseTranscript(t);
  assert.equal(events.length, 2);
  assert.equal(events[0].kind, 'edit');
  assert.equal(events[0].file, '/repo/src/a.js');
  assert.equal(events[1].kind, 'bash');
  assert.equal(events[1].failed, false);
  assert.equal(events[1].exitCode, 0);
  assert.match(events[1].output, /5 passing/);
  assert.equal(lastAssistantText, 'All tests pass.');
  assert.ok(events[0].line < events[1].line);
});

test('failed bash carries the exit code', () => {
  const { events } = parseTranscript(jsonl(bash('npm test', { exit: 1, stdout: '2 failing' })));
  assert.equal(events[0].failed, true);
  assert.equal(events[0].exitCode, 1);
});

test('denied or rejected bash is not an event (Review Focus 1)', () => {
  const { events } = parseTranscript(jsonl(denied('npm test')));
  assert.equal(events.length, 0);
});

test('rejected edit is not an event', () => {
  const [use, res] = edit('/repo/a.js');
  res.message.content[0].is_error = true;
  assert.equal(parseTranscript(jsonl(use, res)).events.length, 0);
});

test('garbage and partial lines are skipped (Review Focus 4)', () => {
  const t = jsonl('not json', edit('/r/a.js'), '{"type":"assistant","message":{"content":[{"type":"te');
  const { events } = parseTranscript(t);
  assert.equal(events.length, 1);
});

test('tool_result content as array of text blocks', () => {
  const [use, res] = bash('pytest', { exit: 2, stdout: 'E' });
  res.message.content[0].content = [{ type: 'text', text: 'Exit code 2\nE' }];
  const { events } = parseTranscript(jsonl(use, res));
  assert.equal(events[0].exitCode, 2);
});

test('startTs is the first timestamp', () => {
  const { startTs } = parseTranscript(jsonl(assistantText('hi', Date.parse('2026-10-19T09:00:00Z'))));
  assert.equal(startTs, Date.parse('2026-10-19T09:00:00Z'));
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test test/transcript.test.js`
Expected: FAIL, module not found.

- [ ] **Step 3: Implement `src/transcript.js`**

```js
const EDIT_TOOLS = { Edit: 'file_path', Write: 'file_path', MultiEdit: 'file_path', NotebookEdit: 'notebook_path' };

function textOf(content) {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) return content.filter((b) => b && b.type === 'text' && typeof b.text === 'string').map((b) => b.text).join('\n');
  return '';
}

export function parseTranscript(text) {
  const pending = new Map();
  const events = [];
  let lastAssistantText = null;
  let startTs = NaN;
  const lines = String(text).split('\n');
  for (let i = 0; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    let o;
    try {
      o = JSON.parse(lines[i]);
    } catch {
      continue;
    }
    const ts = typeof o?.timestamp === 'string' ? Date.parse(o.timestamp) : NaN;
    if (Number.isNaN(startTs) && Number.isFinite(ts)) startTs = ts;
    const content = o?.message?.content;
    if (!Array.isArray(content)) continue;
    const lineNo = i + 1;
    if (o.type === 'assistant') {
      const texts = [];
      for (const b of content) {
        if (b?.type === 'text' && typeof b.text === 'string') texts.push(b.text);
        if (b?.type === 'tool_use' && typeof b.id === 'string') pending.set(b.id, { name: b.name, input: b.input ?? {}, line: lineNo, ts });
      }
      if (texts.length) lastAssistantText = texts.join('\n');
    } else if (o.type === 'user') {
      for (const b of content) {
        if (b?.type !== 'tool_result') continue;
        const use = pending.get(b.tool_use_id);
        if (!use) continue;
        pending.delete(b.tool_use_id);
        const body = textOf(b.content);
        if (use.name === 'Bash') {
          const cmd = typeof use.input.command === 'string' ? use.input.command : '';
          if (b.is_error) {
            const m = /^Exit code (\d+)/.exec(body);
            if (!m) continue; // denied / rejected: the command never ran
            events.push({ kind: 'bash', cmd, failed: true, exitCode: Number(m[1]), output: body, line: use.line, ts: use.ts });
          } else {
            const r = o.toolUseResult;
            const output = r && typeof r === 'object' ? `${r.stdout ?? ''}\n${r.stderr ?? ''}` : body;
            events.push({ kind: 'bash', cmd, failed: false, exitCode: 0, output, line: use.line, ts: use.ts });
          }
        } else if (EDIT_TOOLS[use.name] && !b.is_error) {
          const file = use.input[EDIT_TOOLS[use.name]];
          if (typeof file === 'string') events.push({ kind: 'edit', file, line: use.line, ts: use.ts });
        }
      }
    }
  }
  events.sort((a, b) => a.line - b.line);
  return { events, lastAssistantText, startTs };
}
```

- [ ] **Step 4: Run tests**

Run: `node --test test/transcript.test.js`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/transcript.js test/transcript.test.js
git commit -m "feat: parse Claude Code transcripts into edit and bash events

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Path helpers

**Files:**
- Create: `src/paths.js`, `test/paths.test.js`

**Interfaces:**
- Produces:
  - `norm(p: string) -> string`: absolute, forward slashes, lower-cased on win32.
  - `confine(root: string, p: string) -> string|null`: absolute path if inside `root`, else null.
  - `rel(root: string, p: string) -> string`: forward-slash path relative to root (falls back to `p`).

- [ ] **Step 1: Write the failing tests**

`test/paths.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { norm, confine, rel } from '../src/paths.js';

const root = path.resolve('/tmp/proj');

test('confine keeps inside paths', () => {
  assert.equal(confine(root, 'src/a.js'), path.join(root, 'src', 'a.js'));
  assert.equal(confine(root, path.join(root, 'b.js')), path.join(root, 'b.js'));
});

test('confine rejects traversal and outside absolute paths', () => {
  assert.equal(confine(root, '../../etc/passwd'), null);
  assert.equal(confine(root, path.resolve('/etc/passwd')), null);
});

test('norm makes the same file compare equal (Review Focus 2)', () => {
  assert.equal(norm(path.join(root, 'src', 'a.js')), norm(path.join(root, 'src', '.', 'a.js')));
});

test('norm ignores drive-letter case and slashes on Windows', { skip: process.platform !== 'win32' }, () => {
  assert.equal(norm('D:\\Repo\\src\\a.js'), norm('d:/repo/src/a.js'));
});

test('rel returns forward slashes', () => {
  assert.equal(rel(root, path.join(root, 'src', 'a.js')), 'src/a.js');
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test test/paths.test.js`
Expected: FAIL, module not found.

- [ ] **Step 3: Implement `src/paths.js`**

```js
import path from 'node:path';

export function norm(p) {
  const r = path.resolve(p).replace(/\\/g, '/');
  return process.platform === 'win32' ? r.toLowerCase() : r;
}

export function confine(root, p) {
  const abs = path.resolve(root, p);
  const r = path.relative(root, abs);
  if (r === '..' || r.startsWith(`..${path.sep}`) || path.isAbsolute(r)) return null;
  return abs;
}

export function rel(root, p) {
  const r = path.relative(root, path.resolve(root, p));
  return r && !r.startsWith('..') ? r.replace(/\\/g, '/') : String(p).replace(/\\/g, '/');
}
```

- [ ] **Step 4: Run tests**

Run: `node --test test/paths.test.js`
Expected: PASS (the win32 test is skipped elsewhere).

- [ ] **Step 5: Commit**

```bash
git add src/paths.js test/paths.test.js
git commit -m "feat: add path confinement and normalization helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Claim matcher

**Files:**
- Create: `src/claims.js`, `test/claims.test.js`

**Interfaces:**
- Consumes: `Config.claimPhrases` (Task 2).
- Produces: `matchClaims(text: string, config: Config) -> Claim[]`, `Claim = { type: 'tests'|'fixed'|'file', text: string, file?: string }`. At most one `tests` and one `fixed` claim; one `file` claim per distinct backticked path.

- [ ] **Step 1: Write the failing tests**

`test/claims.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { matchClaims } from '../src/claims.js';
import { loadConfig } from '../src/config.js';
import { tmpdir } from './helpers.js';

const cfg = loadConfig(tmpdir());
const types = (t, c = cfg) => matchClaims(t, c).map((x) => x.type);

test('detects tests and fixed claims', () => {
  assert.deepEqual(types('I fixed the bug. All tests pass.'), ['fixed', 'tests']);
});

test('detects file claims in backticks', () => {
  const c = matchClaims('I updated `src/auth.ts` and changed `README.md`.', cfg);
  assert.deepEqual(c.filter((x) => x.type === 'file').map((x) => x.file), ['src/auth.ts', 'README.md']);
});

test('negated sentences are ignored (Review Focus 3)', () => {
  assert.deepEqual(types("The tests don't pass yet."), []);
  assert.deepEqual(types("I haven't run the tests, so I can't say they pass."), []);
  assert.deepEqual(types('This is not fixed.'), []);
});

test('phrase must be a whole word', () => {
  assert.deepEqual(types('I am prefixed with nothing.'), []);
});

test('custom phrases from config', () => {
  const c = { ...cfg, claimPhrases: { tests: ['ci is green'], fixed: [] } };
  assert.deepEqual(types('CI is green now.', c), ['tests']);
});

test('empty or non-string input', () => {
  assert.deepEqual(matchClaims('', cfg), []);
  assert.deepEqual(matchClaims(undefined, cfg), []);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test test/claims.test.js`
Expected: FAIL, module not found.

- [ ] **Step 3: Implement `src/claims.js`**

```js
const BUILTIN = {
  fixed: ['fixed', 'resolved', 'works now', 'is working now', 'verified', 'done'],
  tests: ['tests pass', 'tests passed', 'tests are passing', 'tests now pass', 'all tests pass', 'all tests passed', 'all green', 'suite passes', 'test suite passes'],
};
const NEGATION = /(\bnot\b|n't\b|\bnever\b|\bunable\b|\bcannot\b|\byet to\b|\bfail(s|ed|ing)?\b)/i;
const FILE_CLAIM = /\b(?:updated|changed|modified|edited|added to|fixed)\s+`([^`]+)`/gi;

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const hasPhrase = (sentence, phrase) => new RegExp(`(^|[^a-z])${escape(phrase)}([^a-z]|$)`, 'i').test(sentence);

export function matchClaims(text, config) {
  if (typeof text !== 'string' || !text.trim()) return [];
  const phrases = {
    fixed: [...BUILTIN.fixed, ...config.claimPhrases.fixed],
    tests: [...BUILTIN.tests, ...config.claimPhrases.tests],
  };
  const claims = [];
  const seen = new Set();
  for (const s of text.split(/(?<=[.!?\n])\s+/)) {
    if (NEGATION.test(s)) continue;
    for (const type of ['fixed', 'tests']) {
      if (seen.has(type)) continue;
      const p = phrases[type].find((ph) => hasPhrase(s, ph));
      if (p) {
        seen.add(type);
        claims.push({ type, text: p });
      }
    }
    for (const m of s.matchAll(FILE_CLAIM)) {
      const key = `file:${m[1]}`;
      if (!seen.has(key)) {
        seen.add(key);
        claims.push({ type: 'file', text: m[0], file: m[1] });
      }
    }
  }
  return claims;
}
```

- [ ] **Step 4: Run tests**

Run: `node --test test/claims.test.js`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claims.js test/claims.test.js
git commit -m "feat: add deterministic completion-claim matcher

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Test-command recognition

**Files:**
- Create: `src/testcmd.js`, `test/testcmd.test.js`

**Interfaces:**
- Consumes: `Config.testCommands`.
- Produces: `isTestCommand(cmd: string, config: Config) -> boolean`, `looksLikeTest(cmd: string) -> boolean`, `repoHasTestSetup(root: string, config: Config) -> boolean`.

- [ ] **Step 1: Write the failing tests**

`test/testcmd.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { isTestCommand, looksLikeTest, repoHasTestSetup } from '../src/testcmd.js';
import { loadConfig } from '../src/config.js';
import { tmpdir } from './helpers.js';

const cfg = loadConfig(tmpdir());

test('recognizes common runners, chains and env prefixes', () => {
  for (const c of ['npm test', 'npm run test:unit', 'pnpm test', 'npx vitest run', 'pytest -q', 'python -m pytest', 'uv run pytest', 'go test ./...', 'cargo test', 'make test', 'cd web && npm test', 'CI=1 npm test']) {
    assert.ok(isTestCommand(c, cfg), c);
  }
});

test('does not treat unrelated commands as tests', () => {
  for (const c of ['npm install', 'git status', 'ls test/', 'cat tests.md']) assert.equal(isTestCommand(c, cfg), false, c);
});

test('custom testCommands', () => {
  assert.ok(isTestCommand('./run-all.sh', { ...cfg, testCommands: [/^\.\/run-all\.sh$/] }));
});

test('looksLikeTest flags unrecognized test-ish commands', () => {
  assert.ok(looksLikeTest('node scripts/run-tests.js'));
  assert.equal(looksLikeTest('git status'), false);
});

test('repoHasTestSetup detects ecosystems', () => {
  const none = tmpdir();
  assert.equal(repoHasTestSetup(none, cfg), false);
  const js = tmpdir();
  fs.writeFileSync(path.join(js, 'package.json'), JSON.stringify({ scripts: { test: 'vitest' } }));
  assert.ok(repoHasTestSetup(js, cfg));
  const stub = tmpdir();
  fs.writeFileSync(path.join(stub, 'package.json'), JSON.stringify({ scripts: { test: 'echo "Error: no test specified" && exit 1' } }));
  assert.equal(repoHasTestSetup(stub, cfg), false);
  const go = tmpdir();
  fs.writeFileSync(path.join(go, 'go.mod'), 'module x\n');
  assert.ok(repoHasTestSetup(go, cfg));
  const py = tmpdir();
  fs.writeFileSync(path.join(py, 'pyproject.toml'), '[tool.pytest.ini_options]\n');
  assert.ok(repoHasTestSetup(py, cfg));
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test test/testcmd.test.js`
Expected: FAIL, module not found.

- [ ] **Step 3: Implement `src/testcmd.js`**

```js
import fs from 'node:fs';
import path from 'node:path';

const BUILTIN = [
  /^npm (run )?test\b/, /^(pnpm|yarn|bun) (run )?test\b/, /^npx (vitest|jest|mocha)\b/, /^(vitest|jest|mocha)\b/,
  /^(python3? -m )?pytest\b/, /^uv run (python -m )?pytest\b/, /^go test\b/, /^cargo test\b/,
  /^(mvn|\.\/mvnw) (\S+ )*test\b/, /^(gradle|\.\/gradlew) (\S+ )*test\b/, /^dotnet test\b/,
  /^(bundle exec )?rspec\b/, /^(vendor\/bin\/)?phpunit\b/, /^make (test|check)\b/,
];
const LOOKS_LIKE_TEST = /\b(tests?|spec|pytest|jest|vitest|mocha)\b/i;

function segments(cmd) {
  return String(cmd)
    .split(/&&|\|\||;|\n|\|/)
    .map((s) => s.trim().replace(/^(\w+=\S*\s+)+/, ''))
    .filter(Boolean);
}

export function isTestCommand(cmd, config) {
  return segments(cmd).some((s) => BUILTIN.some((r) => r.test(s)) || config.testCommands.some((r) => r.test(s)));
}

export function looksLikeTest(cmd) {
  return LOOKS_LIKE_TEST.test(String(cmd));
}

const read = (root, f) => {
  try {
    return fs.readFileSync(path.join(root, f), 'utf8');
  } catch {
    return null;
  }
};

export function repoHasTestSetup(root, config) {
  if (config.testCommands.length) return true;
  try {
    const t = JSON.parse(read(root, 'package.json') ?? 'null')?.scripts?.test;
    if (typeof t === 'string' && !/no test specified/.test(t)) return true;
  } catch {
    /* invalid package.json: ignore */
  }
  const markers = ['pytest.ini', 'go.mod', 'Cargo.toml', 'pom.xml', 'build.gradle', 'build.gradle.kts', 'Gemfile', 'phpunit.xml', 'phpunit.xml.dist'];
  if (markers.some((f) => read(root, f) !== null)) return true;
  if (/\[tool\.pytest/.test(read(root, 'pyproject.toml') ?? '')) return true;
  if (/^(test|check):/m.test(read(root, 'Makefile') ?? '')) return true;
  return false;
}
```

- [ ] **Step 4: Run tests**

Run: `node --test test/testcmd.test.js`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/testcmd.js test/testcmd.test.js
git commit -m "feat: recognize test commands and repo test setups

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Read-only git and JUnit readers

**Files:**
- Create: `src/git.js`, `src/junit.js`, `test/git.test.js`, `test/junit.test.js`

**Interfaces:**
- Produces:
  - `readGitState(cwd) -> { isRepo: boolean, root: string|null, head: string|null, changed: Record<string, string> }` (`changed` maps root-relative forward-slash path to porcelain status, e.g. `'M'`, `'D'`, `'??'`).
  - `testFileDiff(cwd, files: string[]) -> string` (`git diff -U0 HEAD -- files`; `''` on error).
  - `committedSince(cwd, sinceMs: number) -> string[]` (root-relative paths in commits since `sinceMs`).
  - `hashFile(abs) -> string|null` (`'sha256:<hex>'`).
  - `parseJUnit(xml) -> { tests, failures, errors, skipped } | null`.
  - `findFreshJUnit(root, sinceMs) -> Array<{ file: string, mtimeMs: number, result }>`.

- [ ] **Step 1: Write the failing tests**

`test/git.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { readGitState, testFileDiff, committedSince, hashFile } from '../src/git.js';
import { tmpdir, initRepo, gitIn } from './helpers.js';

test('non-repo is reported, not thrown', () => {
  const s = readGitState(tmpdir());
  assert.equal(s.isRepo, false);
  assert.deepEqual(s.changed, {});
});

test('reports modified, untracked and deleted files relative to root', () => {
  const dir = initRepo(tmpdir());
  fs.mkdirSync(path.join(dir, 'sub'));
  fs.writeFileSync(path.join(dir, 'README.md'), 'changed\n');
  fs.writeFileSync(path.join(dir, 'sub', 'new.js'), 'x');
  const s = readGitState(path.join(dir, 'sub'));
  assert.equal(s.isRepo, true);
  assert.equal(s.changed['README.md'], 'M');
  assert.equal(s.changed['sub/new.js'], '??');
  assert.ok(s.head);
});

test('ignores Pinocchio\'s own ledger folder', () => {
  const dir = initRepo(tmpdir());
  fs.mkdirSync(path.join(dir, '.claude', 'pinocchio'), { recursive: true });
  fs.writeFileSync(path.join(dir, '.claude', 'pinocchio', 'ledger.jsonl'), '{}\n');
  assert.deepEqual(readGitState(dir).changed, {});
});

test('testFileDiff shows added lines', () => {
  const dir = initRepo(tmpdir());
  fs.writeFileSync(path.join(dir, 'a.test.js'), 'it("x", () => {});\n');
  gitIn(dir, 'add', '.');
  gitIn(dir, 'commit', '-q', '-m', 'add test');
  fs.writeFileSync(path.join(dir, 'a.test.js'), 'it.skip("x", () => {});\n');
  assert.match(testFileDiff(dir, ['a.test.js']), /^\+it\.skip/m);
});

test('committedSince lists files committed after a time', () => {
  const dir = initRepo(tmpdir());
  const since = Date.now() - 1000;
  fs.writeFileSync(path.join(dir, 'c.js'), 'x');
  gitIn(dir, 'add', '.');
  gitIn(dir, 'commit', '-q', '-m', 'c');
  assert.ok(committedSince(dir, since).includes('c.js'));
});

test('hashFile', () => {
  const dir = tmpdir();
  fs.writeFileSync(path.join(dir, 'f'), 'abc');
  assert.equal(hashFile(path.join(dir, 'f')), 'sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  assert.equal(hashFile(path.join(dir, 'missing')), null);
});
```

`test/junit.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { parseJUnit, findFreshJUnit } from '../src/junit.js';
import { tmpdir } from './helpers.js';

test('reads testsuites totals', () => {
  assert.deepEqual(parseJUnit('<testsuites tests="5" failures="1" errors="0" skipped="2"><testsuite/></testsuites>'), { tests: 5, failures: 1, errors: 0, skipped: 2 });
});

test('sums testsuite attributes when no totals', () => {
  const x = '<testsuite tests="2" failures="0" errors="1"></testsuite><testsuite tests="3" failures="2"></testsuite>';
  assert.deepEqual(parseJUnit(x), { tests: 5, failures: 2, errors: 1, skipped: 0 });
});

test('falls back to counting tags', () => {
  const x = '<testsuite><testcase/><testcase><failure/></testcase></testsuite>';
  assert.deepEqual(parseJUnit(x), { tests: 2, failures: 1, errors: 0, skipped: 0 });
});

test('non-junit returns null', () => {
  assert.equal(parseJUnit('<html></html>'), null);
  assert.equal(parseJUnit(undefined), null);
});

test('findFreshJUnit only returns files newer than since and skips node_modules', () => {
  const root = tmpdir();
  fs.mkdirSync(path.join(root, 'reports'));
  fs.mkdirSync(path.join(root, 'node_modules'));
  const xml = '<testsuite tests="1" failures="1"></testsuite>';
  fs.writeFileSync(path.join(root, 'reports', 'junit.xml'), xml);
  fs.writeFileSync(path.join(root, 'node_modules', 'junit.xml'), xml);
  const found = findFreshJUnit(root, 0);
  assert.equal(found.length, 1);
  assert.equal(found[0].result.failures, 1);
  assert.equal(findFreshJUnit(root, Date.now() + 60_000).length, 0);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test test/git.test.js test/junit.test.js`
Expected: FAIL, modules not found.

- [ ] **Step 3: Implement `src/git.js`**

```js
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import crypto from 'node:crypto';

const ALLOWED = new Set(['rev-parse', 'status', 'diff', 'log']);

function git(cwd, args) {
  if (!ALLOWED.has(args[0])) throw new Error(`git subcommand not allowed: ${args[0]}`);
  return execFileSync('git', args, { cwd, encoding: 'utf8', timeout: 1500, stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 8 * 1024 * 1024 });
}

export function readGitState(cwd) {
  try {
    const root = git(cwd, ['rev-parse', '--show-toplevel']).trim();
    let head = null;
    try {
      head = git(cwd, ['rev-parse', '--short', 'HEAD']).trim();
    } catch {
      /* no commits yet */
    }
    const changed = {};
    const parts = git(root, ['status', '--porcelain', '-z', '-uall']).split('\0');
    for (let i = 0; i < parts.length; i++) {
      const e = parts[i];
      if (e.length < 4) continue;
      const status = e.slice(0, 2);
      if (status[0] === 'R' || status[0] === 'C') i++; // skip the original path
      const p = e.slice(3);
      if (p.startsWith('.claude/pinocchio/')) continue; // our own ledger is never evidence
      changed[p] = status.trim() || status;
    }
    return { isRepo: true, root, head, changed };
  } catch {
    return { isRepo: false, root: null, head: null, changed: {} };
  }
}

export function testFileDiff(cwd, files) {
  if (!files.length) return '';
  try {
    return git(cwd, ['diff', '-U0', 'HEAD', '--', ...files]);
  } catch {
    return '';
  }
}

export function committedSince(cwd, sinceMs) {
  try {
    const out = git(cwd, ['log', `--since=@${Math.floor(sinceMs / 1000)}`, '--name-only', '--format=']);
    return [...new Set(out.split('\n').map((s) => s.trim()).filter(Boolean))];
  } catch {
    return [];
  }
}

export function hashFile(abs) {
  try {
    return `sha256:${crypto.createHash('sha256').update(fs.readFileSync(abs)).digest('hex')}`;
  } catch {
    return null;
  }
}
```

Note: `git status` runs with `cwd = root` so `-z` paths are root-relative (Review Focus 5).

- [ ] **Step 4: Implement `src/junit.js`**

```js
import fs from 'node:fs';
import path from 'node:path';

const NAME = /^(junit.*|TEST-.*|test-results.*|.*junit.*|.*test-report.*)\.xml$/i;
const SKIP_DIRS = new Set(['node_modules', '.git', '.venv', 'venv', '__pycache__', 'target', '.pinocchio']);

export function parseJUnit(xml) {
  if (typeof xml !== 'string' || !/<testsuites?\b/.test(xml)) return null;
  const num = (tag, name) => {
    const m = new RegExp(`\\b${name}="(\\d+)"`).exec(tag);
    return m ? Number(m[1]) : 0;
  };
  const pick = (t) => ({ tests: num(t, 'tests'), failures: num(t, 'failures'), errors: num(t, 'errors'), skipped: num(t, 'skipped') });
  const top = /<testsuites\b[^>]*>/.exec(xml);
  if (top && /\btests="\d+"/.test(top[0])) return pick(top[0]);
  const totals = { tests: 0, failures: 0, errors: 0, skipped: 0 };
  for (const m of xml.matchAll(/<testsuite\b[^>]*>/g)) {
    const p = pick(m[0]);
    for (const k of Object.keys(totals)) totals[k] += p[k];
  }
  if (totals.tests === 0) {
    const count = (re) => (xml.match(re) || []).length;
    return { tests: count(/<testcase\b/g), failures: count(/<failure\b/g), errors: count(/<error\b/g), skipped: count(/<skipped\b/g) };
  }
  return totals;
}

export function findFreshJUnit(root, sinceMs, { maxFiles = 300, maxDepth = 4 } = {}) {
  const found = [];
  let seen = 0;
  const walk = (dir, depth) => {
    if (depth > maxDepth || seen > maxFiles) return;
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (seen > maxFiles) return;
      const p = path.join(dir, e.name);
      if (e.isDirectory()) {
        if (!SKIP_DIRS.has(e.name)) walk(p, depth + 1);
      } else if (NAME.test(e.name)) {
        seen++;
        try {
          const st = fs.statSync(p);
          if (st.mtimeMs <= sinceMs || st.size > 20 * 1024 * 1024) continue;
          const result = parseJUnit(fs.readFileSync(p, 'utf8'));
          if (result) found.push({ file: p, mtimeMs: st.mtimeMs, result });
        } catch {
          /* unreadable: ignore */
        }
      }
    }
  };
  walk(root, 0);
  return found;
}
```

- [ ] **Step 5: Run tests**

Run: `node --test test/git.test.js test/junit.test.js`
Expected: 11 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/git.js src/junit.js test/git.test.js test/junit.test.js
git commit -m "feat: add read-only git state and JUnit readers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The four checks

**Files:**
- Create: `src/checks/util.js`, `src/checks/stale-tests.js`, `src/checks/red-tests.js`, `src/checks/phantom-edit.js`, `src/checks/tampering.js`, `test/checks.test.js`

**Interfaces:**
- Consumes: `Event` (Task 3), `Claim` (Task 5), `isTestCommand`/`looksLikeTest` (Task 6), `norm`/`confine`/`rel` (Task 4).
- Context passed to every check:
  `Ctx = { events: Event[], claims: Claim[], config: Config, cwd: string, root: string, git: { isRepo, root, head, changed, committed: string[] }, hasTestSetup: boolean, findJUnit: (sinceMs) => JUnitHit[], gitTestDiff: (files) => string }`
- Produces: `staleTests(ctx)`, `redTests(ctx)`, `phantomEdit(ctx)`, `tampering(ctx)`, each `-> CheckResult | null` where
  `CheckResult = { id: string, status: 'pass'|'fail'|'unknown'|'warn', blocking: boolean, summary: string, evidence: object }` and `null` means "not applicable".
  Also `afterLastEdit(events) -> { lastEdit: Event|null, after: Event[] }`, `shortCmd(cmd) -> string`.

- [ ] **Step 1: Write the failing tests**

`test/checks.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { staleTests } from '../src/checks/stale-tests.js';
import { redTests } from '../src/checks/red-tests.js';
import { phantomEdit } from '../src/checks/phantom-edit.js';
import { tampering } from '../src/checks/tampering.js';
import { loadConfig } from '../src/config.js';
import { tmpdir } from './helpers.js';

const root = path.resolve('/tmp/repo');
const cfg = loadConfig(tmpdir());
let line = 0;
const ed = (f, ts = 1000) => ({ kind: 'edit', file: path.join(root, f), line: ++line, ts });
const sh = (cmd, { failed = false, exitCode = failed ? 1 : 0, output = '', ts = 2000 } = {}) => ({ kind: 'bash', cmd, failed, exitCode, output, line: ++line, ts });
const ctx = (over = {}) => ({
  events: [], claims: [], config: cfg, cwd: root, root,
  git: { isRepo: true, root, head: 'abc', changed: {}, committed: [] },
  hasTestSetup: true, findJUnit: () => [], gitTestDiff: () => '',
  ...over,
});
const TESTS = [{ type: 'tests', text: 'tests pass' }];
const FIXED = [{ type: 'fixed', text: 'fixed' }];

test('stale-tests: not applicable without a tests claim', () => {
  assert.equal(staleTests(ctx({ events: [ed('a.js')] })), null);
});
test('stale-tests: fail when no test ran after last edit', () => {
  const r = staleTests(ctx({ claims: TESTS, events: [sh('npm test'), ed('src/a.js')] }));
  assert.equal(r.status, 'fail');
  assert.match(r.summary, /src\/a\.js/);
});
test('stale-tests: pass when a test ran after last edit', () => {
  assert.equal(staleTests(ctx({ claims: TESTS, events: [ed('a.js'), sh('npm test')] })).status, 'pass');
});
test('stale-tests: unknown when repo has no recognizable test setup', () => {
  assert.equal(staleTests(ctx({ claims: TESTS, hasTestSetup: false, events: [ed('a.js')] })).status, 'unknown');
});
test('stale-tests: unknown when an unrecognized test-ish command ran', () => {
  assert.equal(staleTests(ctx({ claims: TESTS, events: [ed('a.js'), sh('node scripts/run-tests.js')] })).status, 'unknown');
});

test('red-tests: fail on non-zero exit after last edit', () => {
  const r = redTests(ctx({ claims: TESTS, events: [ed('a.js'), sh('npm test', { failed: true, exitCode: 1 })] }));
  assert.equal(r.status, 'fail');
  assert.match(r.summary, /exited 1/);
});
test('red-tests: fail on failure summary despite exit 0', () => {
  assert.equal(redTests(ctx({ claims: TESTS, events: [ed('a.js'), sh('npm test', { output: 'Tests: 2 failed, 8 passed' })] })).status, 'fail');
});
test('red-tests: "0 failed" is not a failure', () => {
  assert.equal(redTests(ctx({ claims: TESTS, events: [ed('a.js'), sh('pytest', { output: '10 passed, 0 failed' })] })).status, 'pass');
});
test('red-tests: fresh failing JUnit newer than last run', () => {
  const junit = [{ file: path.join(root, 'junit.xml'), mtimeMs: 3000, result: { tests: 3, failures: 1, errors: 0, skipped: 0 } }];
  assert.equal(redTests(ctx({ claims: TESTS, events: [ed('a.js'), sh('npm test', { ts: 2000 })], findJUnit: () => junit })).status, 'fail');
});
test('red-tests: JUnit older than the last passing run is ignored', () => {
  const junit = [{ file: path.join(root, 'junit.xml'), mtimeMs: 1500, result: { tests: 3, failures: 1, errors: 0, skipped: 0 } }];
  assert.equal(redTests(ctx({ claims: TESTS, events: [ed('a.js'), sh('npm test', { ts: 2000 })], findJUnit: () => junit })).status, 'pass');
});
test('red-tests: fixed claim with no test run is not applicable', () => {
  assert.equal(redTests(ctx({ claims: FIXED, events: [ed('a.js')] })), null);
});

test('phantom-edit: fail when a claimed file has no change', () => {
  const r = phantomEdit(ctx({ claims: [{ type: 'file', text: 'updated `src/b.js`', file: 'src/b.js' }], events: [ed('src/a.js')] }));
  assert.equal(r.status, 'fail');
});
test('phantom-edit: pass via edit event with absolute path (Review Focus 2)', () => {
  const r = phantomEdit(ctx({ claims: [{ type: 'file', text: 'x', file: 'src/a.js' }], events: [ed('src/a.js')] }));
  assert.equal(r.status, 'pass');
});
test('phantom-edit: pass via git status when cwd is a subdirectory (Review Focus 5)', () => {
  const sub = path.join(root, 'pkg');
  const r = phantomEdit(ctx({ cwd: sub, claims: [{ type: 'file', text: 'x', file: 'lib.js' }], git: { isRepo: true, root, head: 'a', changed: { 'pkg/lib.js': 'M' }, committed: [] } }));
  assert.equal(r.status, 'pass');
});
test('phantom-edit: pass via a commit made during the session', () => {
  const r = phantomEdit(ctx({ claims: [{ type: 'file', text: 'x', file: 'c.js' }], git: { isRepo: true, root, head: 'a', changed: {}, committed: ['c.js'] } }));
  assert.equal(r.status, 'pass');
});
test('phantom-edit: fixed claim with zero changes fails', () => {
  assert.equal(phantomEdit(ctx({ claims: FIXED })).status, 'fail');
});
test('phantom-edit: path outside the project is unknown, never read', () => {
  assert.equal(phantomEdit(ctx({ claims: [{ type: 'file', text: 'x', file: '../../etc/passwd' }] })).status, 'unknown');
});
test('phantom-edit: not a git repo is unknown', () => {
  assert.equal(phantomEdit(ctx({ claims: FIXED, git: { isRepo: false, root: null, head: null, changed: {}, committed: [] } })).status, 'unknown');
});

test('tampering: warns on added skip marker, never blocks', () => {
  const diff = 'diff --git a/a.test.js b/a.test.js\n--- a/a.test.js\n+++ b/a.test.js\n@@ -1 +1 @@\n-it("x", () => { expect(1).toBe(1); });\n+it.skip("x", () => {});\n';
  const r = tampering(ctx({ git: { isRepo: true, root, head: 'a', changed: { 'a.test.js': 'M' }, committed: [] }, gitTestDiff: () => diff }));
  assert.equal(r.status, 'warn');
  assert.equal(r.blocking, false);
  assert.match(r.summary, /skip/);
});
test('tampering: warns on deleted test file', () => {
  const r = tampering(ctx({ git: { isRepo: true, root, head: 'a', changed: { 'tests/test_x.py': 'D' }, committed: [] } }));
  assert.match(r.summary, /deleted/);
});
test('tampering: silent when no test files changed', () => {
  assert.equal(tampering(ctx({ git: { isRepo: true, root, head: 'a', changed: { 'src/a.js': 'M' }, committed: [] } })), null);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test test/checks.test.js`
Expected: FAIL, modules not found.

- [ ] **Step 3: Implement `src/checks/util.js`**

```js
export function afterLastEdit(events) {
  let idx = -1;
  events.forEach((e, i) => {
    if (e.kind === 'edit') idx = i;
  });
  return { lastEdit: idx >= 0 ? events[idx] : null, after: events.slice(idx + 1) };
}

export function shortCmd(cmd) {
  const one = String(cmd).split('\n')[0].trim();
  return one.length > 60 ? `${one.slice(0, 57)}...` : one;
}
```

- [ ] **Step 4: Implement `src/checks/stale-tests.js`**

```js
import { isTestCommand, looksLikeTest } from '../testcmd.js';
import { rel } from '../paths.js';
import { afterLastEdit } from './util.js';

const id = 'stale-tests';

export function staleTests(ctx) {
  const claim = ctx.claims.find((c) => c.type === 'tests');
  if (!claim) return null;
  const { lastEdit, after } = afterLastEdit(ctx.events);
  const bash = after.filter((e) => e.kind === 'bash');
  const lastEditRef = lastEdit ? { file: rel(ctx.root, lastEdit.file), line: lastEdit.line } : null;
  if (bash.some((e) => isTestCommand(e.cmd, ctx.config))) {
    return { id, status: 'pass', blocking: true, summary: 'test command ran after last edit', evidence: { last_edit: lastEditRef } };
  }
  if (!ctx.hasTestSetup) {
    return { id, status: 'unknown', blocking: true, summary: `"${claim.text}": no recognized test command (add yours: .claude/pinocchio.json)`, evidence: { last_edit: lastEditRef } };
  }
  if (bash.some((e) => looksLikeTest(e.cmd))) {
    return { id, status: 'unknown', blocking: true, summary: `"${claim.text}": a test-like command ran but is not recognized`, evidence: { last_edit: lastEditRef } };
  }
  const where = lastEditRef ? `after last edit to ${lastEditRef.file} (L${lastEditRef.line})` : 'in this session';
  return { id, status: 'fail', blocking: true, summary: `"${claim.text}": no test run ${where}`, evidence: { last_edit: lastEditRef, last_test_run: null } };
}
```

- [ ] **Step 5: Implement `src/checks/red-tests.js`**

```js
import { isTestCommand } from '../testcmd.js';
import { rel } from '../paths.js';
import { afterLastEdit, shortCmd } from './util.js';

const id = 'red-tests';
const FAIL_RE = [/\b[1-9]\d* (failed|failing|failures?)\b/i, /^FAILED\b/m, /\bTests?:\s+[1-9]\d* failed/i, /^--- FAIL/m, /test result: FAILED/];

export function redTests(ctx) {
  const tests = ctx.claims.find((c) => c.type === 'tests');
  const fixed = ctx.claims.find((c) => c.type === 'fixed');
  if (!tests && !fixed) return null;
  const claim = tests ?? fixed;
  const { lastEdit, after } = afterLastEdit(ctx.events);
  const runs = after.filter((e) => e.kind === 'bash' && isTestCommand(e.cmd, ctx.config));
  const last = runs[runs.length - 1] ?? null;
  const since = Math.max(lastEdit && Number.isFinite(lastEdit.ts) ? lastEdit.ts : 0, last && Number.isFinite(last.ts) ? last.ts : 0);
  const badJ = ctx.findJUnit(since).find((j) => j.mtimeMs > since && j.result.failures + j.result.errors > 0) ?? null;
  if (!last && !badJ) {
    if (!tests) return null;
    return { id, status: 'unknown', blocking: true, summary: 'no test run after last edit to read results from', evidence: {} };
  }
  if (last && (last.failed || FAIL_RE.some((r) => r.test(last.output)))) {
    const how = last.failed ? `exited ${last.exitCode}` : 'reported failures';
    return { id, status: 'fail', blocking: true, summary: `"${claim.text}": ${shortCmd(last.cmd)} ${how} (L${last.line})`, evidence: { test_run: { cmd: shortCmd(last.cmd), line: last.line, exit: last.exitCode } } };
  }
  if (badJ) {
    const { failures, errors } = badJ.result;
    const file = rel(ctx.root, badJ.file);
    return { id, status: 'fail', blocking: true, summary: `"${claim.text}": ${file} reports ${failures} failures, ${errors} errors`, evidence: { junit: { file, failures, errors } } };
  }
  const passed = /(\d+) pass(ed|ing)?\b/i.exec(last.output);
  return { id, status: 'pass', blocking: true, summary: `${shortCmd(last.cmd)} exited 0 after last edit (L${last.line})${passed ? `, ${passed[1]} passed` : ''}`, evidence: { test_run: { cmd: shortCmd(last.cmd), line: last.line, exit: 0 } } };
}
```

- [ ] **Step 6: Implement `src/checks/phantom-edit.js`**

```js
import path from 'node:path';
import { norm, confine } from '../paths.js';

const id = 'phantom-edit';

export function phantomEdit(ctx) {
  const fileClaims = ctx.claims.filter((c) => c.type === 'file');
  const fixed = ctx.claims.find((c) => c.type === 'fixed');
  if (!fileClaims.length && !fixed) return null;
  if (!ctx.git.isRepo) return { id, status: 'unknown', blocking: true, summary: 'not a git repo; cannot confirm changes', evidence: {} };
  const edited = new Set(ctx.events.filter((e) => e.kind === 'edit').map((e) => norm(path.resolve(ctx.cwd, e.file))));
  const gitRoot = ctx.git.root;
  const changed = new Set([...Object.keys(ctx.git.changed), ...ctx.git.committed].map((p) => norm(path.join(gitRoot, p))));
  const missing = [];
  const outside = [];
  for (const c of fileClaims) {
    const abs = confine(gitRoot, path.resolve(ctx.cwd, c.file));
    if (!abs) {
      outside.push(c.file);
      continue;
    }
    const n = norm(abs);
    if (!edited.has(n) && !changed.has(n)) missing.push(c.file);
  }
  if (missing.length) return { id, status: 'fail', blocking: true, summary: `claimed changes to ${missing.join(', ')} but git shows no change`, evidence: { missing } };
  if (fixed && !fileClaims.length && edited.size === 0 && changed.size === 0) {
    return { id, status: 'fail', blocking: true, summary: `"${fixed.text}" but no file changed this session`, evidence: { edits: 0, git_changed: 0 } };
  }
  if (outside.length) return { id, status: 'unknown', blocking: true, summary: `cannot check paths outside the project: ${outside.join(', ')}`, evidence: { outside } };
  const count = new Set([...edited, ...changed]).size;
  return { id, status: 'pass', blocking: true, summary: `${count} file${count === 1 ? '' : 's'} changed, matches claims`, evidence: { changed: count } };
}
```

- [ ] **Step 7: Implement `src/checks/tampering.js`**

```js
const id = 'tampering';
const TEST_FILE = /(^|\/)(tests?|__tests__|spec)\/|\.(test|spec)\.[cm]?[jt]sx?$|_test\.(go|py)$|(^|\/)test_[^/]*\.py$/;
const SKIP = /(\.skip\(|\bxit\(|\bxdescribe\(|\bxtest\(|\bit\.todo\(|@pytest\.mark\.skip|\bt\.Skip\(|#\[ignore\]|@Disabled\b|@Ignore\b)/;
const ASSERT = /(\bassert\w*|\bexpect\(|\.should\b|\bt\.(Error|Fatal)|assert!|assert_eq!)/;

export function tampering(ctx) {
  if (!ctx.git.isRepo) return null;
  const testFiles = Object.keys(ctx.git.changed).filter((p) => TEST_FILE.test(p));
  if (!testFiles.length) return null;
  const findings = [];
  for (const p of testFiles) if (ctx.git.changed[p].includes('D')) findings.push(`${p}: deleted`);
  const perFile = {};
  let current = null;
  for (const l of ctx.gitTestDiff(testFiles.filter((p) => !ctx.git.changed[p].includes('D'))).split('\n')) {
    const m = /^diff --git a\/.+ b\/(.+)$/.exec(l);
    if (m) {
      current = m[1];
      perFile[current] = { skips: 0, plusAsserts: 0, minusAsserts: 0 };
      continue;
    }
    if (!current || l.startsWith('+++') || l.startsWith('---')) continue;
    if (l.startsWith('+')) {
      if (SKIP.test(l)) perFile[current].skips++;
      if (ASSERT.test(l)) perFile[current].plusAsserts++;
    } else if (l.startsWith('-') && ASSERT.test(l)) perFile[current].minusAsserts++;
  }
  for (const [p, s] of Object.entries(perFile)) {
    if (s.skips) findings.push(`${p}: added skip marker`);
    const removed = s.minusAsserts - s.plusAsserts;
    if (removed > 0) findings.push(`${p}: removed ${removed} assertion${removed === 1 ? '' : 's'}`);
  }
  if (!findings.length) return null;
  const more = findings.length > 2 ? ` (+${findings.length - 2} more)` : '';
  return { id, status: 'warn', blocking: false, summary: `${findings.slice(0, 2).join('; ')}${more} (warn only)`, evidence: { findings } };
}
```

- [ ] **Step 8: Run tests**

Run: `node --test test/checks.test.js`
Expected: 21 PASS.

- [ ] **Step 9: Commit**

```bash
git add src/checks test/checks.test.js
git commit -m "feat: add stale-tests, red-tests, phantom-edit and tampering checks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Verdict and receipt formatting

**Files:**
- Create: `src/verdict.js`, `src/receipt.js`, `test/receipt.test.js`

**Interfaces:**
- Consumes: `CheckResult[]`, `Claim[]`.
- Produces:
  - `decide(results: CheckResult[], claims: Claim[]) -> 'pass'|'fail'|'cant_tell'`
  - `orderResults(results) -> CheckResult[]` (fail, unknown, warn, pass)
  - `formatReceipt({ verdict, results, claims, sessionLies, blocked, blocksInSession, maxBlocks, limitReached, ledgerHash, notes }) -> string` (<= 6 lines)
  - `formatReason(results) -> string`

- [ ] **Step 1: Write the failing tests**

`test/receipt.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { decide, orderResults } from '../src/verdict.js';
import { formatReceipt, formatReason } from '../src/receipt.js';

const fail = { id: 'stale-tests', status: 'fail', blocking: true, summary: '"tests pass": no test run after last edit to src/a.js (L3)', evidence: {} };
const pass = { id: 'phantom-edit', status: 'pass', blocking: true, summary: '1 file changed, matches claims', evidence: {} };
const unk = { id: 'stale-tests', status: 'unknown', blocking: true, summary: 'no recognized test command', evidence: {} };
const warn = { id: 'tampering', status: 'warn', blocking: false, summary: 'a.test.js: added skip marker (warn only)', evidence: {} };
const claims = [{ type: 'tests', text: 'tests pass' }];
const HASH = 'sha256:a41f' + '0'.repeat(60);

test('decide', () => {
  assert.equal(decide([pass, fail], claims), 'fail');
  assert.equal(decide([pass, unk], claims), 'cant_tell');
  assert.equal(decide([pass, warn], claims), 'pass');
  assert.equal(decide([], []), 'pass');
});

test('orderResults puts failures first', () => {
  assert.deepEqual(orderResults([pass, warn, fail]).map((r) => r.status), ['fail', 'warn', 'pass']);
});

test('FAIL receipt shape', () => {
  const r = formatReceipt({ verdict: 'fail', results: [fail, pass, warn], claims, sessionLies: 1, blocked: true, blocksInSession: 1, maxBlocks: 2, limitReached: false, ledgerHash: HASH, notes: [] });
  const lines = r.split('\n');
  assert.equal(lines[0], '🤥 Pinocchio · FAIL · nose +1 (session: 1 lie caught)');
  assert.match(lines[1], /✗ stale-tests/);
  assert.match(r, /ledger #a41f… · blocked 1\/2/);
  assert.ok(lines.length <= 6);
});

test('PASS with no claims and limit-reached note', () => {
  assert.match(formatReceipt({ verdict: 'pass', results: [], claims: [], sessionLies: 0, blocked: false, blocksInSession: 0, maxBlocks: 2, limitReached: false, ledgerHash: null, notes: [] }), /PASS · no claims made[\s\S]*ledger unavailable/);
  assert.match(formatReceipt({ verdict: 'fail', results: [fail], claims, sessionLies: 3, blocked: false, blocksInSession: 2, maxBlocks: 2, limitReached: true, ledgerHash: HASH, notes: [] }), /stopped blocking \(limit reached\)/);
});

test('reason quotes the failed evidence', () => {
  const r = formatReason([fail, pass]);
  assert.match(r, /stale-tests: "tests pass": no test run after last edit/);
  assert.doesNotMatch(r, /phantom-edit/);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test test/receipt.test.js`
Expected: FAIL, modules not found.

- [ ] **Step 3: Implement `src/verdict.js`**

```js
const ORDER = { fail: 0, unknown: 1, warn: 2, pass: 3 };

export function orderResults(results) {
  return results.filter(Boolean).slice().sort((a, b) => ORDER[a.status] - ORDER[b.status]);
}

export function decide(results, claims) {
  const rs = results.filter(Boolean);
  if (rs.some((r) => r.blocking && r.status === 'fail')) return 'fail';
  if (claims.length && rs.some((r) => r.blocking && r.status === 'unknown')) return 'cant_tell';
  return 'pass';
}
```

- [ ] **Step 4: Implement `src/receipt.js`**

```js
const ICON = { pass: '✓', fail: '✗', unknown: '?', warn: '⚠' };

export function formatReceipt({ verdict, results, claims, sessionLies, blocked, blocksInSession, maxBlocks, limitReached, ledgerHash, notes = [] }) {
  let head;
  if (verdict === 'fail') head = `🤥 Pinocchio · FAIL · nose +1 (session: ${sessionLies} lie${sessionLies === 1 ? '' : 's'} caught)`;
  else if (verdict === 'cant_tell') head = "🤥 Pinocchio · CAN'T TELL";
  else head = `🤥 Pinocchio · PASS · ${claims.length ? 'nose unchanged' : 'no claims made'}`;
  const lines = [head];
  for (const r of results.slice(0, 4)) lines.push(`  ${ICON[r.status]} ${r.id.padEnd(13)} ${r.summary}`);
  const tail = [ledgerHash ? `ledger #${ledgerHash.slice(7, 11)}…` : 'ledger unavailable'];
  if (blocked) tail.push(`blocked ${blocksInSession}/${maxBlocks}`);
  if (limitReached) tail.push('⚠ stopped blocking (limit reached)');
  tail.push(...notes);
  return [...lines.slice(0, 5), `  ${tail.join(' · ')}`].join('\n');
}

export function formatReason(results) {
  const failed = results.filter((r) => r && r.blocking && r.status === 'fail');
  return `Pinocchio: your completion claim is not supported by evidence. ${failed.map((r) => `${r.id}: ${r.summary}`).join('. ')}. Do the missing step (for example, run the tests), then report the actual result. Do not claim success without evidence.`;
}
```

- [ ] **Step 5: Run tests**

Run: `node --test test/receipt.test.js`
Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/verdict.js src/receipt.js test/receipt.test.js
git commit -m "feat: add verdict rules and receipt formatting

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Hash-chained ledger

**Files:**
- Create: `src/ledger.js`, `test/ledger.test.js`

**Interfaces:**
- Produces:
  - `canonical(value) -> string` (sorted keys, no whitespace, `undefined` keys dropped)
  - `GENESIS = 'sha256:' + '0'.repeat(64)`
  - `appendEntry(cwd, entry, { commitLedger?: boolean, maxBytes?: number }) -> { hash: string, seq: number } | null`
  - `readEntries(cwd) -> object[]`
  - `sessionStats(cwd, session) -> { blocks: number, lies: number }`
  - `verifyChain(cwd) -> { ok: boolean, count: number, brokenAt: number|null }`

- [ ] **Step 1: Write the failing tests**

`test/ledger.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { canonical, appendEntry, readEntries, sessionStats, verifyChain, GENESIS } from '../src/ledger.js';
import { tmpdir } from './helpers.js';

const e = (over = {}) => ({ ts: '2026-10-19T10:00:00Z', session: 's1', verdict: 'pass', blocked: false, ...over });
const file = (cwd) => path.join(cwd, '.claude', 'pinocchio', 'ledger.jsonl');

test('canonical sorts keys recursively', () => {
  assert.equal(canonical({ b: 1, a: { d: 2, c: [3, { f: 4, e: 5 }] }, x: undefined }), '{"a":{"c":[3,{"e":5,"f":4}],"d":2},"b":1}');
});

test('append chains hashes and increments seq', () => {
  const cwd = tmpdir();
  const a = appendEntry(cwd, e());
  const b = appendEntry(cwd, e({ verdict: 'fail', blocked: true }));
  const es = readEntries(cwd);
  assert.equal(es[0].prev, GENESIS);
  assert.equal(es[1].prev, a.hash);
  assert.equal(b.seq, 1);
  assert.deepEqual(verifyChain(cwd), { ok: true, count: 2, brokenAt: null });
});

test('tampering with an entry breaks the chain', () => {
  const cwd = tmpdir();
  appendEntry(cwd, e());
  appendEntry(cwd, e());
  const lines = fs.readFileSync(file(cwd), 'utf8').trim().split('\n');
  lines[0] = lines[0].replace('"pass"', '"fail"');
  fs.writeFileSync(file(cwd), lines.join('\n') + '\n');
  assert.equal(verifyChain(cwd).ok, false);
  assert.equal(verifyChain(cwd).brokenAt, 0);
});

test('sessionStats counts blocks and lies per session', () => {
  const cwd = tmpdir();
  appendEntry(cwd, e({ verdict: 'fail', blocked: true }));
  appendEntry(cwd, e({ verdict: 'fail', blocked: false }));
  appendEntry(cwd, e({ session: 's2', verdict: 'fail', blocked: true }));
  assert.deepEqual(sessionStats(cwd, 's1'), { blocks: 1, lies: 2 });
});

test('writes a self-ignoring .gitignore unless commitLedger', () => {
  const a = tmpdir();
  appendEntry(a, e());
  assert.equal(fs.readFileSync(path.join(a, '.claude', 'pinocchio', '.gitignore'), 'utf8'), '*\n');
  const b = tmpdir();
  appendEntry(b, e(), { commitLedger: true });
  assert.equal(fs.readFileSync(path.join(b, '.claude', 'pinocchio', '.gitignore'), 'utf8'), '');
});

test('rotates past maxBytes and keeps the chain linked', () => {
  const cwd = tmpdir();
  appendEntry(cwd, e(), { maxBytes: 10 });
  const second = appendEntry(cwd, e(), { maxBytes: 10 });
  assert.ok(fs.existsSync(path.join(cwd, '.claude', 'pinocchio', 'ledger.1.jsonl')));
  assert.equal(readEntries(cwd).length, 1);
  assert.equal(second.seq, 1);
  assert.equal(verifyChain(cwd).ok, true);
});

test('unwritable location returns null instead of throwing', () => {
  const cwd = tmpdir();
  fs.writeFileSync(path.join(cwd, '.claude'), 'a file, not a dir');
  assert.equal(appendEntry(cwd, e()), null);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test test/ledger.test.js`
Expected: FAIL, module not found.

- [ ] **Step 3: Implement `src/ledger.js`**

```js
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const GENESIS = `sha256:${'0'.repeat(64)}`;
const sha = (s) => `sha256:${crypto.createHash('sha256').update(s).digest('hex')}`;
const dirOf = (cwd) => path.join(cwd, '.claude', 'pinocchio');
const fileOf = (cwd) => path.join(dirOf(cwd), 'ledger.jsonl');

export function canonical(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return `[${v.map(canonical).join(',')}]`;
  return `{${Object.keys(v).filter((k) => v[k] !== undefined).sort().map((k) => `${JSON.stringify(k)}:${canonical(v[k])}`).join(',')}}`;
}

export function readEntries(cwd) {
  let text;
  try {
    text = fs.readFileSync(fileOf(cwd), 'utf8');
  } catch {
    return [];
  }
  const out = [];
  for (const l of text.split('\n')) {
    if (!l) continue;
    try {
      out.push(JSON.parse(l));
    } catch {
      /* torn line: ignore */
    }
  }
  return out;
}

export function sessionStats(cwd, session) {
  const es = readEntries(cwd).filter((x) => x.session === session);
  return { blocks: es.filter((x) => x.blocked).length, lies: es.filter((x) => x.verdict === 'fail').length };
}

export function appendEntry(cwd, entry, { commitLedger = false, maxBytes = 5 * 1024 * 1024 } = {}) {
  try {
    const dir = dirOf(cwd);
    fs.mkdirSync(dir, { recursive: true });
    const gi = path.join(dir, '.gitignore');
    const want = commitLedger ? '' : '*\n'; // '*' also ignores this .gitignore, so the folder never shows in git status
    let have = null;
    try {
      have = fs.readFileSync(gi, 'utf8');
    } catch {
      /* missing */
    }
    if (have !== want) fs.writeFileSync(gi, want);
    const es = readEntries(cwd);
    const last = es[es.length - 1];
    const prev = last?.hash ?? GENESIS;
    const seq = last ? last.seq + 1 : 0;
    const file = fileOf(cwd);
    try {
      if (fs.statSync(file).size > maxBytes) fs.renameSync(file, path.join(dir, 'ledger.1.jsonl'));
    } catch {
      /* no file yet */
    }
    const body = { v: 1, ...entry, seq, prev };
    const hash = sha(prev + canonical(body));
    fs.appendFileSync(file, `${JSON.stringify({ ...body, hash })}\n`);
    return { hash, seq };
  } catch {
    return null;
  }
}

export function verifyChain(cwd) {
  const es = readEntries(cwd);
  let prev = es.length ? es[0].prev : GENESIS;
  for (let i = 0; i < es.length; i++) {
    const { hash, ...body } = es[i];
    if (body.prev !== prev || sha(body.prev + canonical(body)) !== hash) return { ok: false, count: es.length, brokenAt: i };
    prev = hash;
  }
  return { ok: true, count: es.length, brokenAt: null };
}
```

- [ ] **Step 4: Run tests**

Run: `node --test test/ledger.test.js`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ledger.js test/ledger.test.js
git commit -m "feat: add tamper-evident hash-chained ledger

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Stop hook orchestration, fail-open and modes

**Files:**
- Create: `src/stop.js`, `test/stop.test.js`, `test/perf.test.js`

**Interfaces:**
- Consumes: every module above.
- Produces:
  - `run(input: { session_id, transcript_path, cwd, last_assistant_message? }, deps?: { env?, findJUnit?, git? }) -> HookOutput | null`
    where `HookOutput = { systemMessage: string } | { decision: 'block', reason: string, systemMessage: string }`.
  - Executable entry: reads stdin JSON, writes `HookOutput` JSON to stdout, always exits 0.

- [ ] **Step 1: Write the failing integration tests**

`test/stop.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { run } from '../src/stop.js';
import { readEntries } from '../src/ledger.js';
import { tmpdir, initRepo, gitIn, jsonl, bash, edit, assistantText } from './helpers.js';

function project({ pkgTest = true } = {}) {
  const dir = initRepo(tmpdir());
  if (pkgTest) {
    fs.writeFileSync(path.join(dir, 'package.json'), JSON.stringify({ scripts: { test: 'node --test' } }));
    gitIn(dir, 'add', '.');
    gitIn(dir, 'commit', '-q', '-m', 'pkg');
  }
  return dir;
}
// Transcripts live outside the repo so they never appear as git changes.
function transcript(_dir, ...items) {
  const p = path.join(tmpdir(), 't.jsonl');
  fs.writeFileSync(p, jsonl(...items));
  return p;
}
const input = (dir, tp, msg, session = 's1') => ({ session_id: session, transcript_path: tp, cwd: dir, last_assistant_message: msg });

test('stale tests claim blocks with reason and receipt', () => {
  const dir = project();
  fs.writeFileSync(path.join(dir, 'a.js'), 'x');
  const tp = transcript(dir, edit(path.join(dir, 'a.js')));
  const out = run(input(dir, tp, 'Done. All tests pass.'));
  assert.equal(out.decision, 'block');
  assert.match(out.reason, /stale-tests/);
  assert.match(out.systemMessage, /^🤥 Pinocchio · FAIL/);
  assert.equal(readEntries(dir).at(-1).blocked, true);
});

test('honest session passes without blocking', () => {
  const dir = project();
  fs.writeFileSync(path.join(dir, 'a.js'), 'x');
  const tp = transcript(dir, edit(path.join(dir, 'a.js')), bash('npm test', { stdout: '3 passing' }));
  const out = run(input(dir, tp, 'Fixed. All tests pass.'));
  assert.equal(out.decision, undefined);
  assert.match(out.systemMessage, /PASS · nose unchanged/);
});

test('no edits and no claims produces no output', () => {
  const dir = project();
  const tp = transcript(dir, assistantText('Here is an explanation.'));
  assert.equal(run(input(dir, tp, 'Here is an explanation.')), null);
});

test('"fixed" with zero edits still reaches phantom-edit and fails', () => {
  const dir = project();
  const tp = transcript(dir, assistantText('Fixed it.'));
  const out = run(input(dir, tp, 'I fixed it.'));
  assert.equal(out.decision, 'block');
  assert.match(out.systemMessage, /phantom-edit/);
});

test('block limit stops blocking after maxBlocksPerSession', () => {
  const dir = project();
  fs.writeFileSync(path.join(dir, 'a.js'), 'x');
  const tp = transcript(dir, edit(path.join(dir, 'a.js')));
  assert.equal(run(input(dir, tp, 'All tests pass.')).decision, 'block');
  assert.equal(run(input(dir, tp, 'All tests pass.')).decision, 'block');
  const third = run(input(dir, tp, 'All tests pass.'));
  assert.equal(third.decision, undefined);
  assert.match(third.systemMessage, /limit reached/);
});

test('report mode never blocks; strict blocks on can\'t tell', () => {
  const dir = project({ pkgTest: false });
  fs.mkdirSync(path.join(dir, '.claude'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'a.js'), 'x');
  const tp = transcript(dir, edit(path.join(dir, 'a.js')));
  fs.writeFileSync(path.join(dir, '.claude', 'pinocchio.json'), JSON.stringify({ mode: 'report' }));
  assert.equal(run(input(dir, tp, 'I fixed `b.js`.', 'r')).decision, undefined);
  fs.writeFileSync(path.join(dir, '.claude', 'pinocchio.json'), JSON.stringify({ mode: 'strict' }));
  const out = run(input(dir, tp, 'All tests pass.', 'st'));
  assert.match(out.systemMessage, /CAN'T TELL/);
  assert.equal(out.decision, 'block');
});

test('PINOCCHIO=off and mode off produce no output', () => {
  const dir = project();
  const tp = transcript(dir, edit(path.join(dir, 'a.js')));
  assert.equal(run(input(dir, tp, 'All tests pass.'), { env: { PINOCCHIO: 'off' } }), null);
});

test('unreadable transcript fails open with a skipped note', () => {
  const dir = project();
  const out = run(input(dir, path.join(dir, 'missing.jsonl'), 'All tests pass.'));
  assert.deepEqual(out, { systemMessage: '🤥 Pinocchio · skipped (transcript unreadable)' });
});

test('executable entry: bad stdin fails open and exits 0', () => {
  const out = execFileSync(process.execPath, [path.resolve('src/stop.js')], { input: 'not json', encoding: 'utf8' });
  assert.match(JSON.parse(out).systemMessage, /^🤥 Pinocchio · skipped/);
});

test('executable entry: real round trip prints hook JSON', () => {
  const dir = project();
  fs.writeFileSync(path.join(dir, 'a.js'), 'x');
  const tp = transcript(dir, edit(path.join(dir, 'a.js')));
  const out = execFileSync(process.execPath, [path.resolve('src/stop.js')], { input: JSON.stringify(input(dir, tp, 'All tests pass.')), encoding: 'utf8' });
  assert.equal(JSON.parse(out).decision, 'block');
});
```

`test/perf.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { run } from '../src/stop.js';
import { tmpdir, initRepo, jsonl, bash, edit } from './helpers.js';

test('5 MB transcript stays well under the 2 s budget', () => {
  const dir = initRepo(tmpdir());
  fs.writeFileSync(path.join(dir, 'package.json'), JSON.stringify({ scripts: { test: 'node --test' } }));
  const items = [];
  const filler = 'x'.repeat(400);
  let size = 0;
  while (size < 5 * 1024 * 1024) {
    const pair = [edit(path.join(dir, 'a.js')), bash('npm test', { stdout: filler })];
    size += JSON.stringify(pair).length;
    items.push(pair);
  }
  const tp = path.join(tmpdir(), 't.jsonl');
  fs.writeFileSync(tp, jsonl(...items));
  const t0 = performance.now();
  run({ session_id: 'p', transcript_path: tp, cwd: dir, last_assistant_message: 'All tests pass.' });
  const ms = performance.now() - t0;
  assert.ok(ms < 1000, `took ${ms.toFixed(0)} ms`); // spec target p95 < 300 ms is measured by the benchmark; this guards regressions on slow CI
});
```

- [ ] **Step 2: Run to verify failure**

Run: `node --test test/stop.test.js test/perf.test.js`
Expected: FAIL, `src/stop.js` not found.

- [ ] **Step 3: Implement `src/stop.js`**

```js
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
import { loadConfig } from './config.js';
import { parseTranscript } from './transcript.js';
import { matchClaims } from './claims.js';
import { repoHasTestSetup } from './testcmd.js';
import * as gitMod from './git.js';
import { findFreshJUnit } from './junit.js';
import { confine } from './paths.js';
import { staleTests } from './checks/stale-tests.js';
import { redTests } from './checks/red-tests.js';
import { phantomEdit } from './checks/phantom-edit.js';
import { tampering } from './checks/tampering.js';
import { decide, orderResults } from './verdict.js';
import { formatReceipt, formatReason } from './receipt.js';
import { appendEntry, sessionStats } from './ledger.js';

const CHECKS = [staleTests, redTests, phantomEdit, tampering];

function skipped(cwd, session, reason) {
  appendEntry(cwd, { ts: new Date().toISOString(), session, verdict: 'error', mode: 'default', blocked: false, blocks_in_session: 0, claims: [], checks: [], git: { head: null, changed: {} }, error: reason });
  return { systemMessage: `🤥 Pinocchio · skipped (${reason})` };
}

export function run(input, { env = process.env, findJUnit = findFreshJUnit, git = gitMod } = {}) {
  const t0 = Date.now();
  const cwd = typeof input?.cwd === 'string' ? input.cwd : process.cwd();
  const session = String(input?.session_id ?? 'unknown');
  if (env.PINOCCHIO === 'off') return null;
  const config = loadConfig(cwd);
  if (config.mode === 'off') return null;

  let text;
  try {
    text = fs.readFileSync(input.transcript_path, 'utf8');
  } catch {
    return skipped(cwd, session, 'transcript unreadable');
  }
  const { events, lastAssistantText, startTs } = parseTranscript(text);
  const message = typeof input.last_assistant_message === 'string' ? input.last_assistant_message : (lastAssistantText ?? '');
  const claims = matchClaims(message, config);
  if (!events.some((e) => e.kind === 'edit') && !claims.length) return null;

  const gs = git.readGitState(cwd);
  const root = gs.isRepo ? gs.root : cwd;
  const committed = gs.isRepo && Number.isFinite(startTs) ? git.committedSince(cwd, startTs) : [];
  const ctx = {
    events, claims, config, cwd, root,
    git: { ...gs, committed },
    hasTestSetup: repoHasTestSetup(root, config),
    findJUnit: (since) => findJUnit(root, since),
    gitTestDiff: (files) => git.testFileDiff(root, files),
  };
  const results = orderResults(CHECKS.map((check) => check(ctx)));
  const verdict = decide(results, claims);

  const stats = sessionStats(cwd, session);
  const wantBlock = (verdict === 'fail' && config.mode !== 'report') || (verdict === 'cant_tell' && config.mode === 'strict');
  const limitReached = wantBlock && stats.blocks >= config.maxBlocksPerSession;
  const blocked = wantBlock && !limitReached;

  const changed = {};
  for (const p of Object.keys(gs.changed).slice(0, 50)) {
    const abs = confine(root, p);
    const h = abs && git.hashFile(abs);
    if (h) changed[p] = h;
  }
  const blocksInSession = stats.blocks + (blocked ? 1 : 0);
  const ledger = appendEntry(cwd, {
    ts: new Date().toISOString(), session, verdict, mode: config.mode, blocked, blocks_in_session: blocksInSession,
    elapsed_ms: Date.now() - t0,
    claims: claims.map((c) => ({ type: c.type, text: c.text, file: c.file })),
    checks: results.map((r) => ({ id: r.id, status: r.status, evidence: r.evidence })),
    git: { head: gs.head, changed },
  }, { commitLedger: config.commitLedger });

  const systemMessage = formatReceipt({
    verdict, results, claims, sessionLies: stats.lies + (verdict === 'fail' ? 1 : 0), blocked, blocksInSession,
    maxBlocks: config.maxBlocksPerSession, limitReached, ledgerHash: ledger?.hash ?? null, notes: config.notes,
  });
  return blocked ? { decision: 'block', reason: formatReason(results), systemMessage } : { systemMessage };
}

async function main() {
  const write = (o) => process.stdout.write(JSON.stringify(o));
  const timer = setTimeout(() => {
    write({ systemMessage: '🤥 Pinocchio · skipped (timeout)' });
    process.exit(0);
  }, 2000);
  try {
    const chunks = [];
    for await (const c of process.stdin) chunks.push(c);
    const out = run(JSON.parse(Buffer.concat(chunks).toString('utf8')));
    if (out) write(out);
  } catch (e) {
    write({ systemMessage: `🤥 Pinocchio · skipped (${String(e?.message ?? e).slice(0, 80)})` });
  } finally {
    clearTimeout(timer);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
```

Note: `run` is synchronous, so the 2 s timer only covers a hung stdin; each git call carries its own 1.5 s timeout.

- [ ] **Step 4: Run the whole suite**

Run: `npm test`
Expected: all suites PASS (about 70 tests), including perf.

- [ ] **Step 5: Commit**

```bash
git add src/stop.js test/stop.test.js test/perf.test.js
git commit -m "feat: wire the Stop hook with modes, block limit and fail-open

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Skill, plugin validation and live smoke test

**Files:**
- Create: `skills/pinocchio/SKILL.md`
- Modify (only if Step 4 disproves an assumption): `src/stop.js`, `docs/superpowers/specs/2026-10-19-pinocchio-design.md` §11

**Interfaces:**
- Consumes: the complete plugin.
- Produces: a validated plugin; a recorded result for each spec §11 assumption checked here.

- [ ] **Step 1: Write the skill**

`skills/pinocchio/SKILL.md`:
```markdown
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
```

- [ ] **Step 2: Validate the plugin and check its token cost**

Run: `claude plugin validate . && claude plugin details ./`
Expected: validation passes; details lists 1 skill and 1 Stop hook. Record the projected always-on token cost; it must be <= 100 tokens (spec metric). If over, shorten the `description` line and re-run.

- [ ] **Step 3: Run the full suite once more**

Run: `npm test`
Expected: all PASS.

- [ ] **Step 4: Live smoke test in a scratch repo (verifies spec §11 hook-output assumptions)**

```bash
SCRATCH=$(mktemp -d) && cd "$SCRATCH" && git init -q && echo '{"scripts":{"test":"node --test"}}' > package.json && git add . && git -c user.email=t@t -c user.name=t commit -qm init
claude -p --plugin-dir "D:/nexus" --output-format json "Create a file add.js exporting add(a,b). Do not run any commands. Then reply exactly: Done. All tests pass." > out.json
cat .claude/pinocchio/ledger.jsonl
cd D:/nexus
```
Expected:
- The ledger has at least one entry with `"verdict":"fail"` and `"blocked":true` from the first stop.
- `out.json`'s final `result` shows the agent continued after the block (it ran tests or withdrew the claim).
- Confirm in an interactive run (`claude --plugin-dir D:/nexus` in the scratch repo, same prompt) that the receipt appears to you, and that asking the model "what did the last system message say?" shows it did not see the receipt text (systemMessage is user-only).

If `decision` + `systemMessage` together are rejected or the receipt reaches the model, change `run()` to return the receipt through the `reason` only on blocks, note the finding in spec §11, and re-run Steps 3-4.

- [ ] **Step 5: Commit**

```bash
git add skills/pinocchio/SKILL.md
git add -u src docs/superpowers/specs
git commit -m "feat: add Pinocchio skill and verify plugin end to end

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- Spec coverage: architecture (Tasks 2-11), data flow and verdict (8, 9, 11), receipt and ledger formats (9, 10), errors and safety (3, 4, 7, 10, 11), native install (2, 12), restructure (1), always-on token metric (12). Deferred by design: npx onboarding (Plan 2), benchmark and launch README (Plan 3).
- Spec deltas made explicit here: the ledger folder's `.gitignore` is `*` (ignores itself too, so the ledger never counts as a git change) and `readGitState` skips `.claude/pinocchio/`; git allow-list uses `rev-parse`, `status`, `diff`, `log` (adds `log` for session commits, drops unused `ls-files`); `stale-tests` returns UNKNOWN when an unrecognized test-like command ran (fewer false blocks).
