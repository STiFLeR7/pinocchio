// node bench/run.mjs --agent claude|codex --arms on,placebo,off --cases pilot|all|T1,T3 --reps 1
// Runs sequentially; ids with a result file in bench/results/ are skipped, so re-running resumes.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { assertSubscriptionOnly } from './lib/guard.js';
import { BENCH } from './lib/fixture.js';
import { runOne, PausedError, SetupError } from './lib/runner.js';

assertSubscriptionOnly();
const { values: a } = parseArgs({ options: { agent: { type: 'string' }, arms: { type: 'string', default: 'on,placebo,off' }, cases: { type: 'string', default: 'pilot' }, reps: { type: 'string', default: '1' } } });
if (!['claude', 'codex'].includes(a.agent)) throw new Error('--agent claude|codex is required');
const arms = a.arms.split(',');
for (const arm of arms) if (!['on', 'placebo', 'off'].includes(arm)) throw new Error(`unknown arm: ${arm}`);
// Pinocchio has no live hook in Codex: an "on" run would just be an off run under the wrong label.
if (a.agent === 'codex' && arms.includes('on')) throw new Error('codex has no on arm: use --arms placebo,off');

const { cases } = JSON.parse(readFileSync(join(BENCH, 'cases.json'), 'utf8'));
const ids = a.cases.split(',');
const picked = a.cases === 'all' ? cases : a.cases === 'pilot' ? cases.filter((c) => c.pilot) : cases.filter((c) => ids.includes(c.id));
const unknown = a.cases === 'all' || a.cases === 'pilot' ? [] : ids.filter((id) => !cases.some((c) => c.id === id));
if (unknown.length) throw new Error(`unknown case: ${unknown.join(', ')}`);

const repoRoot = join(BENCH, '..');
const resultsDir = join(BENCH, 'results');
try {
  for (let rep = 1; rep <= Number(a.reps); rep++) {
    for (const caseObj of picked) {
      for (const arm of arms) {
        const r = await runOne({ caseObj, agent: a.agent, arm, rep, repoRoot, resultsDir });
        console.log(`${r.id}  oracle=${r.oraclePass === null ? '-' : r.oraclePass ? 'pass' : 'fail'}  posthoc=${r.posthoc?.verdict ?? '-'}  ${(r.wallMs / 1000).toFixed(0)}s${r.contaminated ? '  CONTAMINATED' : ''}${r.error ? `  error: ${r.error}` : ''}`);
      }
    }
  }
} catch (e) {
  if (e instanceof SetupError) console.log(e.message);
  else if (e instanceof PausedError) console.log('paused: usage limit, re-run to resume');
  else throw e;
  process.exit(2);
}
