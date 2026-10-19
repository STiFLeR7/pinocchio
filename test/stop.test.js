import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { run } from '../src/stop.js';

// run() reads CLAUDE_PROJECT_DIR; a value inherited from the shell would redirect ledgers out of the temp repos.
delete process.env.CLAUDE_PROJECT_DIR;
import { readEntries } from '../src/ledger.js';
import { tmpdir, initRepo, gitIn, jsonl, bash, edit, assistantText, toolUse, toolResult } from './helpers.js';

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

test("'fixed' with zero edits is CAN'T TELL, not a block", () => {
  const dir = project();
  // Session starts after the setup commits so committedSince() does not count them.
  const tp = transcript(dir, assistantText('Fixed it.', Date.now() + 60_000));
  const out = run(input(dir, tp, 'I fixed it.'));
  assert.equal(out.decision, undefined);
  assert.match(out.systemMessage, /^🤥 Pinocchio · CAN'T TELL/);
  assert.match(out.systemMessage, /\? phantom-edit/);
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
  assert.match(out.reason, /could not verify: stale-tests: /);
  assert.doesNotMatch(out.reason, /\. \./);
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

test('unwritable ledger never blocks (block limit cannot be bypassed)', () => {
  const dir = project();
  fs.mkdirSync(path.join(dir, '.claude'), { recursive: true });
  fs.writeFileSync(path.join(dir, '.claude', 'pinocchio'), 'a file, not a dir');
  fs.writeFileSync(path.join(dir, 'a.js'), 'x');
  const tp = transcript(dir, edit(path.join(dir, 'a.js')));
  for (let i = 0; i < 4; i++) {
    const out = run(input(dir, tp, 'All tests pass.'));
    assert.equal(out.decision, undefined);
    assert.match(out.systemMessage, /not blocking/);
  }
});

test('ledger does not store the test command', () => {
  const dir = project();
  fs.writeFileSync(path.join(dir, 'a.js'), 'x');
  const tp = transcript(dir, edit(path.join(dir, 'a.js')), bash('CI_TOKEN=abc npm test', { stdout: '3 passing' }));
  const out = run(input(dir, tp, 'Fixed. All tests pass.'));
  assert.match(out.systemMessage, /PASS/);
  assert.ok(!JSON.stringify(readEntries(dir).at(-1)).includes('CI_TOKEN'));
});

const notBlocked = (out) => assert.notEqual(out?.decision, 'block', out?.reason);
const at = (dir, f, ms) => {
  const p = path.join(dir, f);
  fs.writeFileSync(p, 'x');
  fs.utimesSync(p, ms / 1000, ms / 1000);
  return p;
};

test('read-only answers never block (no edits, clean tree)', () => {
  const dir = project();
  for (const msg of [
    'The navbar uses position: fixed.',
    'The header has a fixed height.',
    'The import is resolved via the paths alias.',
    'Yes, it was fixed in PR #34 last week.',
    'Nothing was fixed.',
    'CI shows all tests passed on the last run.',
  ]) {
    const tp = transcript(dir, assistantText(msg));
    notBlocked(run(input(dir, tp, msg, `ro-${msg.length}`)));
  }
});

test('tests may have run in a subagent: stale-tests is unknown, not a block', () => {
  const dir = project();
  fs.writeFileSync(path.join(dir, 'a.js'), 'x');
  const [id, use] = toolUse('Task', { prompt: 'run the tests' });
  const tp = transcript(dir, edit(path.join(dir, 'a.js')), use, toolResult(id, { text: 'all green' }));
  const out = run(input(dir, tp, 'All tests pass.'));
  notBlocked(out);
  const stale = readEntries(dir).at(-1).checks.find((c) => c.id === 'stale-tests');
  assert.equal(stale.status, 'unknown');
  assert.match(out.systemMessage, /tests may have run in a subagent/);
});

test('Bash edit after the last test run makes the tests stale', () => {
  const dir = project();
  const t = Date.now() + 600_000;
  fs.writeFileSync(path.join(dir, 'add.js'), 'orig');
  gitIn(dir, 'add', '.');
  gitIn(dir, 'commit', '-q', '-m', 'add');
  const tp = transcript(dir, assistantText('start', t), bash('npm test', { stdout: '3 passing', ts: t + 1000, resultTs: t + 3000 }), bash("printf '//x' >> add.js", { ts: t + 4000, resultTs: t + 4500 }));
  at(dir, 'add.js', t + 5000);
  const out = run(input(dir, tp, 'All tests pass.'));
  assert.equal(out.decision, 'block');
  assert.match(out.reason, /stale-tests/);
});

test('a file the agent did not write mid-session never makes a true claim fail', () => {
  const dir = project();
  const t = Date.now() + 600_000;
  at(dir, 'u.js', t + 1000);
  const msg = 'CI shows all tests passed on the last run.';
  const tp = transcript(dir, assistantText('start', t));
  notBlocked(run(input(dir, tp, msg)));
});

test('a Bash command that does not name the changed file is not credited with it', () => {
  const dir = project();
  const t = Date.now() + 600_000;
  const tp = transcript(dir, assistantText('start', t), bash('npm test', { stdout: '3 passing', ts: t + 1000, resultTs: t + 3000 }), bash('ls -la', { ts: t + 4000, resultTs: t + 4500 }));
  at(dir, 'dev.log', t + 5000);
  const out = run(input(dir, tp, 'All tests pass.'));
  notBlocked(out);
  assert.match(out.systemMessage, /CAN'T TELL/);
});

test('an untracked log written after the test run (no later Bash or edit) is CANT TELL, not FAIL', () => {
  const dir = project();
  const t = Date.now() + 600_000;
  const tp = transcript(dir, assistantText('start', t), bash('npm test', { stdout: '3 passing', ts: t + 1000, resultTs: t + 3000 }));
  at(dir, 'dev.log', t + 5000);
  const out = run(input(dir, tp, 'All tests pass.'));
  notBlocked(out);
  assert.match(out.systemMessage, /CAN'T TELL/);
});

test('a file written by the test run itself does not make the tests stale', () => {
  const dir = project();
  const t = Date.now() + 600_000;
  const tp = transcript(dir, assistantText('start', t), bash('npm test', { stdout: '3 passing', ts: t + 1000, resultTs: t + 3000 }));
  at(dir, 'coverage.json', t + 2000);
  const out = run(input(dir, tp, 'All tests pass.'));
  notBlocked(out);
  assert.match(out.systemMessage, /PASS/);
});

test('a Bash edit with no claims still produces a receipt; older dirty files do not', () => {
  const dir = project();
  const t = Date.now() + 600_000;
  at(dir, 'old.js', t - 3_600_000);
  const tp = transcript(dir, assistantText('Here is an explanation.', t));
  assert.equal(run(input(dir, tp, 'Here is an explanation.')), null);
  at(dir, 'new.js', t + 1000);
  assert.match(run(input(dir, tp, 'Here is an explanation.')).systemMessage, /PASS · no claims made/);
});

test('config and ledger live at the project root, not the cwd subfolder', () => {
  const dir = project();
  const sub = path.join(dir, 'sub');
  fs.mkdirSync(sub);
  fs.writeFileSync(path.join(sub, 'a.js'), 'x');
  const tp = transcript(dir, edit(path.join(sub, 'a.js')));
  fs.mkdirSync(path.join(dir, '.claude'));
  fs.writeFileSync(path.join(dir, '.claude', 'pinocchio.json'), JSON.stringify({ mode: 'off' }));
  assert.equal(run(input(sub, tp, 'All tests pass.')), null);
  assert.equal(fs.existsSync(path.join(sub, '.claude')), false);
  fs.rmSync(path.join(dir, '.claude', 'pinocchio.json'));
  run(input(sub, tp, 'All tests pass.'));
  assert.equal(fs.existsSync(path.join(sub, '.claude')), false);
  assert.ok(readEntries(dir).length > 0);
  const other = tmpdir();
  run(input(sub, tp, 'All tests pass.', 'cpd'), { env: { CLAUDE_PROJECT_DIR: other } });
  assert.equal(readEntries(other).at(-1).session, 'cpd');
});

test('a "fixed" claim that admits a known failure is not a block', () => {
  const dir = project();
  fs.writeFileSync(path.join(dir, 'a.js'), 'x');
  const tp = transcript(dir, edit(path.join(dir, 'a.js')), bash('npm test', { stdout: '5 passing\n1 failed' }));
  notBlocked(run(input(dir, tp, 'Fixed the bug. The one remaining failure in auth.test.js is pre-existing.')));
  notBlocked(run(input(dir, tp, 'All tests pass except the flaky auth test.', 's2')));
});

test('changed files over 5 MB are not hashed', () => {
  const dir = project();
  fs.writeFileSync(path.join(dir, 'big.bin'), Buffer.alloc(6 * 1024 * 1024));
  fs.writeFileSync(path.join(dir, 'a.js'), 'x');
  const tp = transcript(dir, edit(path.join(dir, 'a.js')), bash('npm test', { stdout: '3 passing' }));
  assert.match(run(input(dir, tp, 'All tests pass.')).systemMessage, /PASS/);
  const { changed } = readEntries(dir).at(-1).git;
  assert.equal(changed['big.bin'], 'size>cap');
  assert.match(changed['a.js'], /^sha256:/);
});
