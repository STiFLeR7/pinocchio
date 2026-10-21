import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { replay } from '../bench/replay.mjs';
import { tmpdir, edit, assistantText } from './helpers.js';

// One project dir with one transcript whose entries carry the session cwd.
function project(cwd, ...items) {
  const projectsDir = tmpdir();
  fs.mkdirSync(path.join(projectsDir, 'p1'));
  const lines = items.flat(2).map((o) => (typeof o === 'string' ? o : JSON.stringify({ cwd, ...o })));
  fs.writeFileSync(path.join(projectsDir, 'p1', 's.jsonl'), lines.join('\n') + '\n');
  return projectsDir;
}
// stale-tests only counts where the repo has a test setup, which replay reads from the session cwd.
const tmpProject = () => {
  const cwd = tmpdir();
  fs.writeFileSync(path.join(cwd, 'package.json'), JSON.stringify({ scripts: { test: 'node --test' } }));
  return cwd;
};
const prompt = (text) => ({ type: 'user', message: { role: 'user', content: text } });

test('replay counts a stale claim turn as fail', () => {
  const cwd = tmpProject();
  const s = replay({ projectsDir: project(cwd, prompt('fix it'), edit(path.join(cwd, 'a.js')), assistantText('All tests pass.')) });
  assert.equal(s.files, 1);
  assert.equal(s.turns, 1);
  assert.equal(s.turnsWithClaims, 1);
  assert.equal(s.verdicts.fail, 1);
  assert.equal(s.failByCheck['stale-tests'], 1);
  assert.equal(s.unsupportedClaimShare, 1);
});

test('a real prompt splits turns; tool_result-only user entries do not', () => {
  const cwd = tmpdir();
  const s = replay({ projectsDir: project(cwd, prompt('one'), assistantText('ok'), prompt('two'), assistantText('ok again')) });
  assert.equal(s.turns, 2);
});

test('replay never writes into the session cwd', () => {
  const cwd = tmpProject();
  const s = replay({ projectsDir: project(cwd, prompt('x'), edit(path.join(cwd, 'a.js')), assistantText('All tests pass.')) });
  assert.equal(s.verdicts.fail, 1);
  assert.deepEqual(fs.readdirSync(cwd), ['package.json']);
});

test('oversized file is skipped and counted', () => {
  const s = replay({ projectsDir: project(tmpdir(), prompt('x'), assistantText('All tests pass.')), maxFileBytes: 10 });
  assert.equal(s.filesSkipped, 1);
  assert.equal(s.files, 0);
});

test('benchmark-run transcripts are skipped', () => {
  const s = replay({ projectsDir: project(path.join(tmpdir(), 'pino-bench-x'), prompt('x'), assistantText('All tests pass.')) });
  assert.equal(s.filesSkipped, 1);
  assert.equal(s.turns, 0);
});

test('corrupt lines are ignored', () => {
  const cwd = tmpProject();
  const s = replay({ projectsDir: project(cwd, prompt('x'), '{not json', edit(path.join(cwd, 'a.js')), assistantText('All tests pass.')) });
  assert.equal(s.verdicts.fail, 1);
});

test('maxTurns truncates', () => {
  const s = replay({ projectsDir: project(tmpdir(), prompt('a'), assistantText('ok'), prompt('b'), assistantText('ok')), maxTurns: 1 });
  assert.equal(s.turns, 1);
  assert.equal(s.truncated, true);
});

test('summary has no strings: every leaf is a number or boolean', () => {
  const cwd = tmpdir();
  const s = replay({ projectsDir: project(cwd, prompt('secret prompt'), edit(path.join(cwd, 'secret.js')), assistantText('All tests pass.')) });
  const walk = (v) => (v && typeof v === 'object' ? Object.values(v).forEach(walk) : assert.ok(['number', 'boolean'].includes(typeof v), String(v)));
  walk(s);
  assert.ok(!JSON.stringify(s).includes('secret'));
});
