import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';

export function statePath(scope, projectDir, home = homedir()) {
  return join(scope === 'user' ? home : projectDir, '.claude', 'pinocchio', 'install.json');
}

// Missing or unparseable state reads as "nothing recorded".
export function readState(file) {
  try { return JSON.parse(readFileSync(file, 'utf8')); } catch { return null; }
}

export function writeState(file, state) {
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, JSON.stringify(state, null, 2) + '\n');
}

export function sha256File(path) {
  try { return createHash('sha256').update(readFileSync(path)).digest('hex'); } catch { return null; }
}
