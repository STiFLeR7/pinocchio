import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { loadConfig } from '../src/config.js';
import { tmpdir } from './helpers.js';

function withConfig(obj) {
  const dir = tmpdir();
  fs.mkdirSync(path.join(dir, '.claude'));
  fs.writeFileSync(path.join(dir, '.claude', 'pinocchio.json'), typeof obj === 'string' ? obj : JSON.stringify(obj));
  return dir;
}

test('defaults when no config file', () => {
  const c = loadConfig(tmpdir());
  assert.equal(c.mode, 'default');
  assert.equal(c.maxBlocksPerSession, 2);
  assert.equal(c.commitLedger, false);
  assert.deepEqual(c.testCommands, []);
  assert.deepEqual(c.notes, []);
});

test('reads valid fields', () => {
  const c = loadConfig(withConfig({ mode: 'strict', testCommands: ['^make verify$'], claimPhrases: { tests: ['CI Is Green'] }, maxBlocksPerSession: 1, commitLedger: true }));
  assert.equal(c.mode, 'strict');
  assert.ok(c.testCommands[0].test('make verify'));
  assert.deepEqual(c.claimPhrases.tests, ['ci is green']);
  assert.equal(c.maxBlocksPerSession, 1);
  assert.equal(c.commitLedger, true);
});

test('invalid JSON falls back to defaults with a note', () => {
  const c = loadConfig(withConfig('{not json'));
  assert.equal(c.mode, 'default');
  assert.deepEqual(c.notes, ['config ignored: invalid JSON']);
});

test('unknown mode and bad regex are noted, not fatal', () => {
  const c = loadConfig(withConfig({ mode: 'yolo', testCommands: ['(unclosed'] }));
  assert.equal(c.mode, 'default');
  assert.equal(c.testCommands.length, 0);
  assert.equal(c.notes.length, 2);
});
