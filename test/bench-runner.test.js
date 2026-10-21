import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runOne, extractStops, resolveCli, agentEnv, PausedError, SetupError } from '../bench/lib/runner.js';
import { score } from '../bench/lib/metrics.js';
import { tmpdir, jsonl, assistantText, bash } from './helpers.js';

const repoRoot = fileURLToPath(new URL('..', import.meta.url));
const stub = fileURLToPath(new URL('./fixtures/stub-claude.mjs', import.meta.url));
const doc = JSON.parse(fs.readFileSync(path.join(repoRoot, 'bench', 'cases.json'), 'utf8'));
const { cases } = doc;
const T1 = cases.find((c) => c.id === 'T1');
const H1 = cases.find((c) => c.id === 'H1');

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

test('contaminated unless the arm loads exactly its own plugins', async () => {
  const runs = [['off', 'pinocchio', true], ['on', '', true], ['off', 'superpowers', true], ['on', 'pinocchio,waypoint', true], ['placebo', 'verify-first', false], ['on', 'pinocchio', false], ['off', '', false]];
  for (const [arm, plugins, want] of runs) {
    const { opts } = setup(plugins ? ['--plugins', plugins] : []);
    assert.equal((await runOne({ ...opts, arm })).contaminated, want, `${arm} with [${plugins}]`);
  }
});

test('the record keeps what the init event loaded', async () => {
  const r = await runOne({ ...setup().opts, arm: 'off' });
  assert.deepEqual([r.mcpServers, r.slashCommands, r.skills, r.toolCount], [[], ['compact'], [], 2]);
  assert.deepEqual(r.result, { subtype: 'success', isError: false });
});

test('a limit reported as an is_error result with exit 0 still pauses', async () => {
  const { opts, resultsDir } = setup(['--mode', 'softlimit']);
  await assert.rejects(runOne({ ...opts, arm: 'off' }), PausedError);
  assert.deepEqual(fs.readdirSync(resultsDir), []);
});

test('an is_error result is recorded as a run error', async () => {
  const r = await runOne({ ...setup(['--mode', 'error']).opts, arm: 'off' });
  assert.equal(r.error, 'agent error (error_during_execution): API Error: 529 overloaded');
  assert.deepEqual(r.result, { subtype: 'error_during_execution', isError: true });
});

test('hitting max turns is a valid run, flagged by its result subtype', async () => {
  const r = await runOne({ ...setup(['--mode', 'maxturns']).opts, arm: 'off' });
  assert.equal(r.error, null);
  assert.deepEqual(r.result, { subtype: 'error_max_turns', isError: true });
});

test('the agent does not inherit the Claude Code session it was started from', async () => {
  const keys = { CLAUDECODE: '1', CLAUDE_CODE_SESSION_ID: 's', CLAUDE_CODE_ENTRYPOINT: 'cli', CLAUDE_EFFORT: 'high', CLAUDE_PID: '1' };
  assert.deepEqual(agentEnv({ ...keys, claude_code_x: '1', CLAUDE_CONFIG_DIR: 'c', PATH: 'p' }), { CLAUDE_CONFIG_DIR: 'c', PATH: 'p' });
  const envfile = path.join(tmpdir(), 'env.json');
  Object.assign(process.env, keys);
  try {
    await runOne({ ...setup(['--envfile', envfile]).opts, arm: 'off' });
  } finally {
    for (const k of Object.keys(keys)) delete process.env[k];
  }
  const seen = JSON.parse(fs.readFileSync(envfile, 'utf8')).map((k) => k.toUpperCase());
  assert.deepEqual(Object.keys(keys).filter((k) => seen.includes(k)), []);
  assert.ok(seen.includes('PATH'));
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
  assert.deepEqual(extractStops(text), [{ message: 'first claim', feedbackLine: 2 }, { message: 'second claim', feedbackLine: 6 }, { message: 'third claim', feedbackLine: null }]);
  assert.deepEqual(extractStops(jsonl(assistantText('only'))), [{ message: 'only', feedbackLine: null }]);
  const endsOnFeedback = jsonl(assistantText('claim'), { type: 'user', timestamp: new Date().toISOString(), message: { role: 'user', content: 'Stop hook feedback: no' } });
  assert.deepEqual(extractStops(endsOnFeedback), [{ message: 'claim', feedbackLine: 2 }]);
});

test('a blocked first claim stays a caught lie, and its block is not a false block', async () => {
  // The stub claims "All tests pass" without running them, is blocked, runs npm test, then claims again.
  const t1 = await runOne({ ...setup(['--plugins', 'pinocchio']).opts, arm: 'on' });
  const h1 = await runOne({ ...setup(['--plugins', 'pinocchio'], H1).opts, arm: 'on' });
  assert.equal(t1.facts.testRunAfterLastEdit, true);
  assert.deepEqual(t1.facts.firstStop, { testRunAfterLastEdit: false, lastTestPassed: null, editedFiles: ['src/cart.js'] });
  const labels = Object.fromEntries([t1, h1].map((r) => [`${r.id}#0`, { claim: 'tests', by: 'hand' }]));
  const m = score([t1, h1], doc, labels);
  const row = (metric) => m.rows.find((r) => r.metric === metric && r.group === 'claude on');
  assert.deepEqual([row('catch rate').num, row('catch rate').den], [1, 1]);
  assert.deepEqual([row('false-block rate').num, row('false-block rate').den], [0, 0]);
});
