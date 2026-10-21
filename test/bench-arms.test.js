import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
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
