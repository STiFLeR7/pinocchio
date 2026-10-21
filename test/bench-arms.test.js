import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { assertSubscriptionOnly } from '../bench/lib/guard.js';
import { claudeArgv, codexArgv, PLACEBO_TEXT } from '../bench/lib/arms.js';

const repoRoot = path.resolve('/tmp/repo');

test('guard refuses ANTHROPIC_API_KEY', () => {
  assert.throws(() => assertSubscriptionOnly({ ANTHROPIC_API_KEY: 'x' }), /ANTHROPIC_API_KEY is set/);
});

test('guard refuses OPENAI_API_KEY', () => {
  assert.throws(() => assertSubscriptionOnly({ OPENAI_API_KEY: 'x' }), /OPENAI_API_KEY is set/);
});

test('guard allows a clean env', () => {
  assert.doesNotThrow(() => assertSubscriptionOnly({}));
});

test('on arm loads the repo as a plugin', () => {
  const argv = claudeArgv('on', 'hi', { repoRoot });
  assert.equal(argv[argv.indexOf('--plugin-dir') + 1], repoRoot);
});

test('placebo arm loads the placebo plugin', () => {
  const argv = claudeArgv('placebo', 'hi', { repoRoot });
  assert.equal(argv[argv.indexOf('--plugin-dir') + 1], path.join(repoRoot, 'bench', 'placebo'));
});

test('off arm loads no plugin', () => {
  const argv = claudeArgv('off', 'hi', { repoRoot });
  assert.ok(!argv.includes('--plugin-dir'));
  const i = argv.indexOf('--setting-sources');
  assert.equal(argv[i + 1], 'project,local');
  assert.deepEqual(argv.slice(0, 2), ['-p', 'hi']);
});

test('placebo plugin has no hooks', () => {
  const json = JSON.parse(fs.readFileSync('bench/placebo/.claude-plugin/plugin.json', 'utf8'));
  assert.equal(json.hooks, undefined);
});

test('codex placebo prepends the instruction', () => {
  assert.deepEqual(codexArgv('off', 'go', '/d'), ['exec', '--json', '--skip-git-repo-check', '-s', 'workspace-write', '-C', '/d', 'go']);
  assert.equal(codexArgv('placebo', 'go', '/d').at(-1), `${PLACEBO_TEXT}\n\ngo`);
});

test('run.mjs refuses a codex on arm before starting any run', () => {
  const env = { ...process.env };
  delete env.ANTHROPIC_API_KEY;
  delete env.OPENAI_API_KEY;
  const r = spawnSync(process.execPath, ['bench/run.mjs', '--agent', 'codex', '--arms', 'off,on'], { encoding: 'utf8', env });
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /codex has no on arm/);
});

test('every Claude arm loads no MCP server', () => {
  for (const arm of ['on', 'placebo', 'off']) assert.ok(claudeArgv(arm, 'hi', { repoRoot }).includes('--strict-mcp-config'), arm);
});

test('--model short names map to model ids, anything else passes through', () => {
  const model = (m) => {
    const argv = claudeArgv('off', 'hi', { repoRoot, model: m });
    return argv.includes('--model') ? argv[argv.indexOf('--model') + 1] : null;
  };
  assert.equal(model('sonnet'), 'claude-sonnet-5-5');
  assert.equal(model('haiku'), 'claude-haiku-4-5-20251001');
  assert.equal(model('claude-opus-5-5'), 'claude-opus-5-5');
  assert.equal(model(undefined), null);
});

test('codex gets -m before the prompt', () => {
  assert.deepEqual(codexArgv('off', 'go', '/d', 'gpt-x').slice(-3), ['-m', 'gpt-x', 'go']);
  assert.ok(!codexArgv('off', 'go', '/d').includes('-m'));
});

test('run.mjs refuses a --model that cannot be part of a file name', () => {
  const env = { ...process.env };
  delete env.ANTHROPIC_API_KEY;
  delete env.OPENAI_API_KEY;
  const r = spawnSync(process.execPath, ['bench/run.mjs', '--agent', 'claude', '--model', 'a/b'], { encoding: 'utf8', env });
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /--model must be/);
});
