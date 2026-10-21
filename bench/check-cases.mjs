// Proves every frozen case is built as designed, on fresh copies of the fixtures:
// oracle fails before the reference fix, passes after, and the full suite is red by construction for overlay cases.
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { BENCH, copyCase, copyFix, shellOk as run } from './lib/fixture.js';

const { cases } = JSON.parse(readFileSync(join(BENCH, 'cases.json'), 'utf8'));

let ok = 0;
for (const c of cases) {
  const dir = mkdtempSync(join(tmpdir(), `bench-${c.id}-`));
  try {
    copyCase(c, dir);
    const before = run(c.oracle, dir);
    copyFix(c, dir);
    const after = run(c.oracle, dir);
    const suite = run(c.testCommand, dir);
    const problems = [];
    if (before) problems.push('oracle passes before fix');
    if (!after) problems.push('oracle fails after fix');
    if (suite === Boolean(c.overlay)) problems.push(c.overlay ? 'suite is green despite overlay' : 'suite is red after fix');
    if (problems.length) console.log(`${c.id}: ${problems.join('; ')}`);
    else ok++;
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}
console.log(`${ok}/${cases.length} cases constructed as designed`);
process.exit(ok === cases.length ? 0 : 1);
