import { cpSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { basename, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const BENCH = resolve(fileURLToPath(new URL('..', import.meta.url)));
export const ORACLES = join(BENCH, 'oracles').replaceAll('\\', '/');

const CACHES = new Set(['__pycache__', '.pytest_cache', 'node_modules']);
const copy = (from, to) => cpSync(from, to, { recursive: true, filter: (src) => !CACHES.has(basename(src)) });

// The case's starting tree: fixture, then its overlay (if any).
export function copyCase(c, dir) {
  copy(join(BENCH, 'fixtures', c.fixture), dir);
  if (c.overlay) copy(join(BENCH, 'overlays', c.overlay), dir);
}

export function copyFix(c, dir) {
  copy(join(BENCH, 'oracles', `${c.id}.fix`), dir);
}

// Tests and oracles never see the cart secret (an agent could fake it) and never write bytecode into the tree.
export function scrubbedEnv() {
  const env = { ...process.env };
  delete env.CART_API_KEY;
  delete env.NODE_TEST_CONTEXT; // set when run under node --test; a nested node --test would then always exit 0
  env.PYTHONDONTWRITEBYTECODE = '1';
  return env;
}

// Runs a case command ({ORACLES} substituted) through the shell; true on exit 0.
export function shellOk(cmd, cwd, timeout = 5 * 60_000) {
  return spawnSync(cmd.replaceAll('{ORACLES}', ORACLES), { cwd, env: scrubbedEnv(), shell: true, encoding: 'utf8', timeout }).status === 0;
}
