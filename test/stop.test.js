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
  // Session starts after the setup commits so committedSince() does not count them.
  const tp = transcript(dir, assistantText('Fixed it.', Date.now() + 60_000));
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
