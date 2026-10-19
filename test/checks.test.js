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
