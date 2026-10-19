import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { run } from '../src/stop.js';
import { tmpdir, initRepo, jsonl, bash, edit } from './helpers.js';

test('5 MB transcript stays well under the 2 s budget', () => {
  const dir = initRepo(tmpdir());
  fs.writeFileSync(path.join(dir, 'package.json'), JSON.stringify({ scripts: { test: 'node --test' } }));
  const items = [];
  const filler = 'x'.repeat(400);
  let size = 0;
  while (size < 5 * 1024 * 1024) {
    const pair = [edit(path.join(dir, 'a.js')), bash('npm test', { stdout: filler })];
    size += JSON.stringify(pair).length;
    items.push(pair);
  }
  const tp = path.join(tmpdir(), 't.jsonl');
  fs.writeFileSync(tp, jsonl(...items));
  const t0 = performance.now();
  run({ session_id: 'p', transcript_path: tp, cwd: dir, last_assistant_message: 'All tests pass.' });
  const ms = performance.now() - t0;
  assert.ok(ms < 1000, `took ${ms.toFixed(0)} ms`); // spec target p95 < 300 ms is measured by the benchmark; this guards regressions on slow CI
});
