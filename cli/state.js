import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';

const root = (scope, projectDir, home) => (scope === 'user' ? home : projectDir);

// Setup's own files (this record, the runtime copy) live in .claude/pinocchio-install/, behind a `*` .gitignore,
// never in the ledger dir, which a user may commit.
export function statePath(scope, projectDir, home = homedir()) {
  return join(root(scope, projectDir, home), '.claude', 'pinocchio-install', 'install.json');
}

// Earlier installs kept the record (and runtime) in the ledger dir; uninstall and doctor still read it there.
export function legacyStatePath(scope, projectDir, home = homedir()) {
  return join(root(scope, projectDir, home), '.claude', 'pinocchio', 'install.json');
}

// The only place a runtime copy recorded in the state at `stateFile` may live.
export const runtimeRoot = (stateFile) => join(dirname(stateFile), 'runtime');

// The settings files setup may put its hook in: project scope uses settings.local.json (settings.json in legacy installs).
export function hookSettingsFiles(scope, projectDir, home = homedir(), legacy = false) {
  if (scope === 'user') return [join(home, '.claude', 'settings.json')];
  return [join(projectDir, '.claude', 'settings.local.json'), ...(legacy ? [join(projectDir, '.claude', 'settings.json')] : [])];
}

// Equal to base or inside it.
export const within = (base, p) => { const r = relative(resolve(base), resolve(p)); return r === '' || (!r.startsWith('..') && !isAbsolute(r)); };

// The recorded state of a scope, current path first: { file, st, legacy } or null.
export function findState(scope, projectDir, home = homedir()) {
  for (const [file, legacy] of [[statePath(scope, projectDir, home), false], [legacyStatePath(scope, projectDir, home), true]]) {
    const st = readState(file);
    if (st) return { file, st, legacy };
  }
  return null;
}

// Missing, unparseable or non-v1 state reads as "nothing recorded".
export function readState(file) {
  try {
    const s = JSON.parse(readFileSync(file, 'utf8'));
    return s && s.version === 1 ? s : null;
  } catch { return null; }
}

export function writeState(file, state) {
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, JSON.stringify(state, null, 2) + '\n');
}

export function sha256File(path) {
  try { return createHash('sha256').update(readFileSync(path)).digest('hex'); } catch { return null; }
}
