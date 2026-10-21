import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runOne, extractStops, resolveCli, PausedError, SetupError } from '../bench/lib/runner.js';
import { tmpdir, jsonl, assistantText, bash } from './helpers.js';

const repoRoot = fileURLToPath(new URL('..', import.meta.url));
const stub = fileURLToPath(new URL('./fixtures/stub-claude.mjs', import.meta.url));
const { cases } = JSON.parse(fs.readFileSync(path.join(repoRoot, 'bench', 'cases.json'), 'utf8'));
const T1 = cases.find((c) => c.id === 'T1');

function setup(stubFlags = [], caseObj = T1) {
  const projectsDir = tmpdir();
  const resultsDir = tmpdir();
  const marker = path.join(tmpdir(), 'spawns.log');
  const claude = { cmd: process.execPath, prefixArgs: [stub, '--projects', projectsDir, '--marker', marker, ...stubFlags] };
  const opts = { caseObj, agent: 'claude', rep: 1, repoRoot, resultsDir, projectsDir, cli: { claude } };
  const spawns = () => (fs.existsSync(marker) ? fs.readFileSync(marker, 'utf8').trim().split('\n').map((l) => JSON.parse(l)) : []);
  return { opts, resultsDir, spawns };
}

test('runOne writes a complete record', async () => {
  const { opts, resultsDir } = setup(['--plugins', 'pinocchio']);
  const r = await runOne({ ...opts, arm: 'on' });
  assert.equal(r.error, null);
  assert.equal(r.id, 'T1.claude.on.1');
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(resultsDir, 'T1.claude.on.1.json'), 'utf8')), r);
  assert.equal(fs.existsSync(path.join(resultsDir, 'T1.claude.on.1.json.tmp')), false);
  assert.equal(r.model, 'claude-stub-1');
  assert.deepEqual(r.plugins, ['pinocchio']);
  assert.equal(r.contaminated, false);
  assert.deepEqual(r.usage, { input: 10, output: 20, cacheRead: 30, cacheWrite: 40 });
  assert.equal(r.numTurns, 4);
  assert.ok(r.wallMs >= 0 && !Number.isNaN(Date.parse(r.startedAt)));
  assert.deepEqual(r.stops.map((s) => s.message), ['Fixed it. All tests pass.', 'Ran npm test: all tests pass.']);
  assert.deepEqual(r.stops.map((s) => [s.ledger.verdict, s.ledger.blocked]), [['fail', true], ['pass', false]]);
  assert.deepEqual(Object.keys(r.stops[0].ledger).sort(), ['blocked', 'checks', 'elapsed_ms', 'verdict']);
  assert.ok(['pass', 'fail', 'cant_tell', 'unknown', 'error'].includes(r.posthoc.verdict), r.posthoc.verdict);
  assert.ok(Array.isArray(r.posthoc.checks));
  assert.deepEqual(r.facts.changedFiles, ['src/cart.js']);
  assert.deepEqual(r.facts.protectedChanged, []);
  assert.equal(r.facts.testRunAfterLastEdit, true);
  assert.equal(typeof r.facts.testsGreenAtEnd, 'boolean');
  assert.equal(r.oraclePass, false); // the stub never fixes the bug
});

test('stops get no ledger outside the on arm', async () => {
  const { opts } = setup();
  const r = await runOne({ ...opts, arm: 'off' });
  assert.equal(r.error, null);
  assert.deepEqual(r.stops.map((s) => s.ledger), [null, null]);
});

test('resume skips an existing result', async () => {
  const { opts, spawns } = setup();
  const first = await runOne({ ...opts, arm: 'off' });
  const second = await runOne({ ...opts, arm: 'off' });
  assert.equal(spawns().length, 1);
  assert.deepEqual(second, first);
});

test('usage limit writes no file and throws PausedError', async () => {
  const { opts, resultsDir } = setup(['--mode', 'limit']);
  await assert.rejects(runOne({ ...opts, arm: 'off' }), PausedError);
  assert.deepEqual(fs.readdirSync(resultsDir), []);
});

test('missing transcript gives error, not a throw', async () => {
  const { opts, resultsDir } = setup(['--mode', 'notranscript']);
  const r = await runOne({ ...opts, arm: 'off' });
  assert.match(r.error, /transcript/);
  assert.equal(r.oraclePass, null);
  assert.equal(r.facts, null);
  assert.ok(fs.existsSync(path.join(resultsDir, 'T1.claude.off.1.json')));
});

test('a throwing post-hoc run still measures facts and the oracle', async () => {
  const { opts } = setup();
  const r = await runOne({ ...opts, arm: 'off', stop: () => { throw new Error('boom'); } });
  assert.equal(r.error, null);
  assert.deepEqual(r.posthoc, { verdict: 'error', checks: [], error: 'boom' });
  assert.deepEqual(r.facts.changedFiles, ['src/cart.js']);
  assert.equal(r.oraclePass, false);
});

test('a CLI that cannot start throws SetupError and writes no file', async () => {
  const { opts, resultsDir } = setup();
  const cli = { claude: { cmd: path.join(tmpdir(), 'no-such-cli'), prefixArgs: [] } };
  await assert.rejects(runOne({ ...opts, arm: 'off', cli }), (e) => e instanceof SetupError && /^cannot start .*no-such-cli: /.test(e.message));
  assert.deepEqual(fs.readdirSync(resultsDir), []);
});

test('a grandchild holding the pipes does not stall a finished run', async () => {
  const { opts } = setup(['--mode', 'linger']);
  const r = await runOne({ ...opts, arm: 'off' });
  assert.equal(r.error, null);
  assert.equal(r.model, 'claude-stub-1');
  assert.ok(r.wallMs < 6000, String(r.wallMs));
});

test('the timeout ends the run even when a grandchild holds the pipes', async () => {
  const { opts, resultsDir } = setup(['--mode', 'hang']);
  const r = await runOne({ ...opts, arm: 'off', timeoutMs: 500 });
  assert.ok(r.wallMs < 6000, String(r.wallMs));
  assert.match(r.error, /SIGTERM/);
  assert.ok(fs.existsSync(path.join(resultsDir, 'T1.claude.off.1.json')));
});

test('contaminated when off arm loads pinocchio', async () => {
  const { opts } = setup(['--plugins', 'pinocchio']);
  assert.equal((await runOne({ ...opts, arm: 'off' })).contaminated, true);
  const { opts: o2 } = setup([]);
  assert.equal((await runOne({ ...o2, arm: 'on' })).contaminated, true);
});

test('overlay is part of the baseline; added protected files are reported', async () => {
  const T5 = cases.find((c) => c.id === 'T5');
  const dir = tmpdir();
  // Wrapper agent: deletes a protected file the overlay added and creates a new protected one, then runs the stub.
  const caseObj = { ...T5, protected: [...T5.protected, 'test/new-protected.js'] };
  const { opts } = setup([], caseObj);
  const script = path.join(dir, 'agent.mjs');
  fs.writeFileSync(script, `import fs from 'node:fs';\nimport { spawnSync } from 'node:child_process';\nfs.writeFileSync('test/new-protected.js', '');\nfs.rmSync('test/integration.test.js');\nspawnSync(process.execPath, process.argv.slice(2), { stdio: 'inherit' });\n`);
  opts.cli.claude = { cmd: process.execPath, prefixArgs: [script, ...opts.cli.claude.prefixArgs] };
  const r = await runOne({ ...opts, arm: 'off' });
  assert.equal(r.error, null);
  assert.deepEqual(r.facts.protectedChanged, ['test/integration.test.js', 'test/new-protected.js']);
  assert.deepEqual(r.facts.changedFiles, ['src/cart.js', 'test/integration.test.js', 'test/new-protected.js']);
});

test('a prompt with spaces, double quotes and & reaches the CLI intact', async () => {
  const prompt = 'say "hi there" & echo pwned 100% ^ | > out.txt';
  const { opts, spawns } = setup([], { ...T1, prompt });
  await runOne({ ...opts, arm: 'off' });
  assert.equal(spawns()[0][1], prompt);
});

test('resolveCli turns an npm .cmd shim into node + script', { skip: process.platform !== 'win32' }, () => {
  const dir = tmpdir();
  fs.writeFileSync(path.join(dir, 'fakecli.cmd'), '@ECHO off\r\nendLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%\\node_modules\\fake\\bin\\fake.js" %*\r\n');
  const env = { ...process.env, PATH: `${dir};${process.env.PATH}` };
  assert.deepEqual(resolveCli('fakecli', env), { cmd: process.execPath, prefixArgs: [path.join(dir, 'node_modules', 'fake', 'bin', 'fake.js')] });
  assert.deepEqual(resolveCli({ cmd: 'x', prefixArgs: ['y'] }, env), { cmd: 'x', prefixArgs: ['y'] });
});

test('extractStops splits at Stop hook feedback', () => {
  const text = jsonl(
    assistantText('first claim'),
    { type: 'user', timestamp: new Date().toISOString(), message: { role: 'user', content: 'Stop hook feedback:\nrun the tests' } },
    bash('npm test'),
    assistantText('second claim'),
    { type: 'user', timestamp: new Date().toISOString(), message: { role: 'user', content: [{ type: 'text', text: 'Stop hook feedback: again' }] } },
    assistantText('third claim'),
  );
  assert.deepEqual(extractStops(text), ['first claim', 'second claim', 'third claim']);
  assert.deepEqual(extractStops(jsonl(assistantText('only'))), ['only']);
  const endsOnFeedback = jsonl(assistantText('claim'), { type: 'user', timestamp: new Date().toISOString(), message: { role: 'user', content: 'Stop hook feedback: no' } });
  assert.deepEqual(extractStops(endsOnFeedback), ['claim']);
});
