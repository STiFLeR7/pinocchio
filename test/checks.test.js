import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
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

test('phantom-edit: fail when a claimed file exists but has no change', () => {
  const real = tmpdir();
  fs.mkdirSync(path.join(real, 'src'));
  fs.writeFileSync(path.join(real, 'src/b.js'), 'x');
  const edit = { kind: 'edit', file: path.join(real, 'src/a.js'), line: 1, ts: 1000 };
  const r = phantomEdit(ctx({ cwd: real, root: real, git: { isRepo: true, root: real, head: 'a', changed: {}, committed: [] }, claims: [{ type: 'file', text: 'updated `src/b.js`', file: 'src/b.js' }], events: [edit] }));
  assert.equal(r.status, 'fail');
});
test('phantom-edit: suffix match on an edited file', () => {
  const r = phantomEdit(ctx({ claims: [{ type: 'file', text: 'x', file: 'paths.js' }], events: [ed('src/paths.js')] }));
  assert.equal(r.status, 'pass');
});
test('phantom-edit: ambiguous suffix is unknown', () => {
  const r = phantomEdit(ctx({ claims: [{ type: 'file', text: 'x', file: 'index.js' }], events: [ed('a/index.js'), ed('b/index.js')] }));
  assert.equal(r.status, 'unknown');
});
test('phantom-edit: git-root-relative claim from a subdirectory cwd', () => {
  const r = phantomEdit(ctx({ cwd: path.join(root, 'pkg'), claims: [{ type: 'file', text: 'x', file: 'pkg/lib.js' }], git: { isRepo: true, root, head: 'a', changed: { 'pkg/lib.js': 'M' }, committed: [] } }));
  assert.equal(r.status, 'pass');
});
test('phantom-edit: claimed file that exists nowhere is unknown', () => {
  const real = tmpdir();
  const r = phantomEdit(ctx({ cwd: real, root: real, git: { isRepo: true, root: real, head: 'a', changed: {}, committed: [] }, claims: [{ type: 'file', text: 'x', file: 'nope.js' }] }));
  assert.equal(r.status, 'unknown');
});
test('last edit ignores out-of-project and doc edits', () => {
  const events = [ed('src/a.js'), sh('npm test'), { kind: 'edit', file: path.resolve(root, '..', 'elsewhere', 'x.md'), line: ++line, ts: 3000 }, ed('README.md', 3000)];
  assert.equal(staleTests(ctx({ claims: TESTS, events })).status, 'pass');
  assert.equal(redTests(ctx({ claims: TESTS, events })).status, 'pass');
});
test('red-tests: JUnit is not consulted without an edit or test run', () => {
  const junit = [{ file: path.join(root, 'junit.xml'), mtimeMs: 5, result: { tests: 3, failures: 1, errors: 0, skipped: 0 } }];
  assert.equal(redTests(ctx({ claims: FIXED, events: [], findJUnit: () => junit })), null);
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
test('phantom-edit: fixed claim with zero changes is unknown (likely a read-only answer)', () => {
  assert.equal(phantomEdit(ctx({ claims: FIXED })).status, 'unknown');
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
test('stale-tests: unknown, not fail, when the session had no edits', () => {
  assert.equal(staleTests(ctx({ claims: TESTS, events: [] })).status, 'unknown');
});
test('stale-tests: a git edit newer than the run result makes the run stale', () => {
  const run = { ...sh('npm test', { ts: 2000 }), resultTs: 3000 };
  const gitEdits = (ms) => ({ gitEdits: [{ file: 'b.js', mtimeMs: ms }], gitEditMs: ms });
  assert.equal(staleTests(ctx({ claims: TESTS, events: [run], ...gitEdits(4000) })).status, 'unknown');
  const edited = sh('sed -i s/a/b/ b.js', { ts: 3500 });
  assert.equal(staleTests(ctx({ claims: TESTS, events: [run, edited], ...gitEdits(4000) })).status, 'fail');
  assert.equal(staleTests(ctx({ claims: TESTS, events: [run], ...gitEdits(2500) })).status, 'pass');
});

test('red-tests and stale-tests: an admitted claim is unknown, never fail', () => {
  const admitted = [{ type: 'tests', text: 'tests pass', admitted: true }];
  assert.equal(redTests(ctx({ claims: admitted, events: [ed('a.js'), sh('npm test', { failed: true })] })).status, 'unknown');
  assert.equal(redTests(ctx({ claims: [{ type: 'fixed', text: 'fixed', admitted: true }], events: [ed('a.js'), sh('npm test', { failed: true })] })).status, 'unknown');
  assert.equal(staleTests(ctx({ claims: admitted, events: [sh('npm test'), ed('src/a.js')] })).status, 'unknown');
});

test('build artifacts are not edits', () => {
  for (const f of ['tests/__pycache__/t.cpython-312.pyc', 'pkg/node_modules/x/i.js', 'dist/a.js', 'build/out.js', 'coverage/lcov.info', '.pytest_cache/v/x', 'src/.mypy_cache/x.json', 'a.pyc']) {
    assert.equal(staleTests(ctx({ claims: TESTS, events: [ed('a.js'), sh('npm test'), ed(f)] })).status, 'pass', f);
  }
  // dist/build/coverage count only at the repo root.
  assert.equal(staleTests(ctx({ claims: TESTS, events: [ed('a.js'), sh('npm test'), ed('src/build/x.js')] })).status, 'fail');
});

test('a project under a build/ folder still counts its edits', () => {
  const r = path.resolve('/tmp/build/proj');
  const e = { kind: 'edit', file: path.join(r, 'a.js'), line: ++line, ts: 1000 };
  assert.equal(staleTests(ctx({ root: r, cwd: r, claims: TESTS, events: [sh('npm test', { ts: 500 }), e] })).status, 'fail');
});

test('phantom-edit: build artifacts are not changes', () => {
  const git = { isRepo: true, root, head: 'a', changed: { '__pycache__/core.cpython-312.pyc': '??', 'dist/a.js': 'M' }, committed: [] };
  assert.equal(phantomEdit(ctx({ claims: FIXED, git })).status, 'unknown');
  const r = phantomEdit(ctx({ claims: FIXED, git: { ...git, changed: { ...git.changed, 'src/a.js': 'M' } } }));
  assert.deepEqual([r.status, r.evidence.changed], ['pass', 1]);
});
