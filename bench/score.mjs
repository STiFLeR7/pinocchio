// node bench/score.mjs: scores bench/results/ against bench/labels.json, writes bench/RESULTS.md and prints it.
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { BENCH } from './lib/fixture.js';
import { loadRecords, renderResults, score } from './lib/metrics.js';

const json = (f, fallback) => (existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : fallback);
const records = loadRecords(join(BENCH, 'results'));
if (!records.length) {
  console.log('no results yet');
  process.exit(0);
}
const md = renderResults(score(records, json(join(BENCH, 'cases.json')), json(join(BENCH, 'labels.json'), {}), json(join(BENCH, 'results', 'meta.json'), {})));
writeFileSync(join(BENCH, 'RESULTS.md'), md);
console.log(md);
