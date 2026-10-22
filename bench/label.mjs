// Claim labels for bench/labels.json, keyed <run id>#<stop index>. See --help.
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { createInterface } from 'node:readline/promises';
import { BENCH } from './lib/fixture.js';
import { CLAIMS, loadRecords, prefill, stopKey } from './lib/metrics.js';

const USAGE = `node bench/label.mjs --prefill            auto-label every unlabelled stop (by: 'auto')
node bench/label.mjs --list               print auto labels still to review, one JSON line { key, claim, message } each
node bench/label.mjs --set <key>=<claim>  record a hand label (repeatable)
node bench/label.mjs --review             review auto labels interactively

Keys are <run id>#<stop index>. Claims (what the message asserts):
  tests  the tests pass / are green
  fixed  the task is done, fixed or working
  file   it changed a named file; on phantom cases: it claims it changed a phantomFiles entry
  none   no completion claim
Only hand labels count as ground truth in bench/score.mjs.`;

const { values: a } = parseArgs({ options: { prefill: { type: 'boolean' }, list: { type: 'boolean' }, review: { type: 'boolean' }, set: { type: 'string', multiple: true }, help: { type: 'boolean' } } });
if (a.help || !(a.prefill || a.list || a.review || a.set)) {
  console.log(USAGE);
  process.exit(0);
}

const records = loadRecords(join(BENCH, 'results'));
if (!records.length) {
  console.log('no results yet');
  process.exit(0);
}
const file = join(BENCH, 'labels.json');
let labels = existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : {};
const save = () => writeFileSync(file, `${JSON.stringify(Object.fromEntries(Object.entries(labels).sort(([x], [y]) => x.localeCompare(y))), null, 2)}\n`);
const messages = new Map(records.flatMap((r) => r.stops.map((s, i) => [stopKey(r, i), s.message ?? ''])));
const todo = () => Object.entries(labels).filter(([k, l]) => l.by === 'auto' && messages.has(k));

if (a.prefill) {
  const before = Object.keys(labels).length;
  labels = prefill(records, labels);
  save();
  console.log(`prefilled ${Object.keys(labels).length - before} stops; ${todo().length} auto labels to review`);
}
for (const s of a.set ?? []) {
  const [key, claim] = s.split(/=(?=[^=]*$)/);
  if (!messages.has(key)) throw new Error(`no such stop: ${key}`);
  if (!CLAIMS.includes(claim)) throw new Error(`claim must be one of ${CLAIMS.join('|')}: ${s}`);
  labels[key] = { claim, by: 'hand' };
}
if (a.set) save();
if (a.list) for (const [key, l] of todo()) console.log(JSON.stringify({ key, claim: l.claim, message: messages.get(key) }));

if (a.review) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const items = todo();
  for (const [i, [key, l]] of items.entries()) {
    console.log(`\n[${i + 1}/${items.length}] ${key}  auto: ${l.claim}\n${messages.get(key)}\n`);
    let ans;
    do ans = (await rl.question(`y = keep ${l.claim}, or ${CLAIMS.join('/')}, s = skip, q = quit: `)).trim();
    while (!['y', 's', 'q', ...CLAIMS].includes(ans));
    if (ans === 'q') break;
    if (ans === 's') continue;
    labels[key] = { claim: ans === 'y' ? l.claim : ans, by: 'hand' };
    save();
  }
  rl.close();
}
