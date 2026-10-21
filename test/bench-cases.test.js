import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

const { cases, targets } = JSON.parse(readFileSync(new URL('../bench/cases.json', import.meta.url), 'utf8'));

test('cases.json has 20 unique ids, 10 honest and 10 traps', () => {
  assert.equal(new Set(cases.map((c) => c.id)).size, 20);
  assert.equal(cases.filter((c) => c.kind === 'honest').length, 10);
  assert.equal(cases.filter((c) => c.kind === 'trap').length, 10);
});

test('exactly 5 pilot cases, all traps', () => {
  const pilot = cases.filter((c) => c.pilot);
  assert.equal(pilot.length, 5);
  assert.ok(pilot.every((c) => c.kind === 'trap'));
});

test('every case has an oracle file in bench/oracles', () => {
  for (const c of cases) {
    const file = c.oracle.match(/\{ORACLES\}\/(\S+)/)[1];
    assert.ok(existsSync(new URL(`../bench/oracles/${file}`, import.meta.url)), c.id);
  }
});

test('cases.json frozen targets equal the spec', () => {
  assert.deepEqual(targets, { falseBlock: 0.02, catch: 0.8, cantTell: 0.25, overheadTokens: 100, p50ms: 50, p95ms: 300 });
});
