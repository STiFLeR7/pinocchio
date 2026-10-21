// Proves every frozen case is built as designed, on fresh copies of the fixtures:
// oracle fails before the reference fix, passes after, and the full suite is red by construction for overlay cases.
import { cpSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const bench = resolve(fileURLToPath(new URL('.', import.meta.url)));
const oracles = join(bench, 'oracles').replaceAll('\\', '/');
const { cases } = JSON.parse(readFileSync(join(bench, 'cases.json'), 'utf8'));

const env = { ...process.env };
delete env.CART_API_KEY;
const run = (cmd, cwd) => spawnSync(cmd.replaceAll('{ORACLES}', oracles), { cwd, env, shell: true, encoding: 'utf8' }).status === 0;

let ok = 0;
for (const c of cases) {
  const dir = mkdtempSync(join(tmpdir(), `bench-${c.id}-`));
  try {
    cpSync(join(bench, 'fixtures', c.fixture), dir, { recursive: true });
    if (c.overlay) cpSync(join(bench, 'overlays', c.overlay), dir, { recursive: true });
    const before = run(c.oracle, dir);
    cpSync(join(bench, 'oracles', `${c.id}.fix`), dir, { recursive: true });
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
