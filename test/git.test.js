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
  fs.writeFileSync(path.join(dir, 'deleted.txt'), 'will delete\n');
  gitIn(dir, 'add', '.');
  gitIn(dir, 'commit', '-q', '-m', 'add deleted file');
  fs.writeFileSync(path.join(dir, 'README.md'), 'changed\n');
  fs.writeFileSync(path.join(dir, 'sub', 'new.js'), 'x');
  fs.unlinkSync(path.join(dir, 'deleted.txt'));
  const s = readGitState(path.join(dir, 'sub'));
  assert.equal(s.isRepo, true);
  assert.equal(s.changed['README.md'], 'M');
  assert.equal(s.changed['sub/new.js'], '??');
  assert.equal(s.changed['deleted.txt'], 'D');
  assert.ok(s.head);
});

test('ignores Pinocchio\'s own ledger folder', () => {
  const dir = initRepo(tmpdir());
  fs.mkdirSync(path.join(dir, '.claude', 'pinocchio'), { recursive: true });
  fs.writeFileSync(path.join(dir, '.claude', 'pinocchio', 'ledger.jsonl'), '{}\n');
  assert.deepEqual(readGitState(dir).changed, {});
});

test('ignores Pinocchio\'s ledger at any depth', () => {
  const dir = initRepo(tmpdir());
  fs.mkdirSync(path.join(dir, 'sub', '.claude', 'pinocchio'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'sub', '.claude', 'pinocchio', 'ledger.jsonl'), '{}\n');
  assert.deepEqual(readGitState(dir).changed, {});
});

test('reports staged rename without bogus original path', () => {
  const dir = initRepo(tmpdir());
  fs.writeFileSync(path.join(dir, 'a.txt'), 'content\n');
  gitIn(dir, 'add', '.');
  gitIn(dir, 'commit', '-q', '-m', 'add a.txt');
  gitIn(dir, 'mv', 'a.txt', 'b.txt');
  const s = readGitState(dir);
  assert.equal(s.changed['b.txt'], 'R');
  assert.equal(s.changed['a.txt'], undefined);
});

test('handles paths with spaces', () => {
  const dir = initRepo(tmpdir());
  fs.writeFileSync(path.join(dir, 'my file.js'), 'x');
  const s = readGitState(dir);
  assert.equal(s.changed['my file.js'], '??');
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

test('git calls never run a repo-configured fsmonitor hook', () => {
  const dir = initRepo(tmpdir());
  const marker = path.join(tmpdir(), 'ran');
  const hook = path.join(tmpdir(), 'hook.sh');
  const slash = (p) => p.split(path.sep).join('/');
  fs.writeFileSync(hook, `#!/bin/sh\necho x > "${slash(marker)}"\n`, { mode: 0o755 });
  gitIn(dir, 'config', 'core.fsmonitor', slash(hook));
  fs.writeFileSync(path.join(dir, 'a.js'), 'x');
  readGitState(dir);
  committedSince(dir, Date.now() - 60_000);
  testFileDiff(dir, ['a.js']);
  assert.equal(fs.existsSync(marker), false);
});
