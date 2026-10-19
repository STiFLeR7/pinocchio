import fs from 'node:fs';
import path from 'node:path';

const MODES = new Set(['default', 'report', 'strict', 'off']);

function defaults() {
  return { mode: 'default', testCommands: [], claimPhrases: { tests: [], fixed: [] }, maxBlocksPerSession: 2, commitLedger: false, notes: [] };
}

export function loadConfig(cwd) {
  const cfg = defaults();
  let raw;
  try {
    raw = fs.readFileSync(path.join(cwd, '.claude', 'pinocchio.json'), 'utf8');
  } catch {
    return cfg;
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    cfg.notes.push('config ignored: invalid JSON');
    return cfg;
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    cfg.notes.push('config ignored: not an object');
    return cfg;
  }
  if (parsed.mode !== undefined) {
    if (MODES.has(parsed.mode)) cfg.mode = parsed.mode;
    else cfg.notes.push(`config: unknown mode "${parsed.mode}", using default`);
  }
  if (Array.isArray(parsed.testCommands)) {
    for (const s of parsed.testCommands) {
      try {
        cfg.testCommands.push(new RegExp(s));
      } catch {
        cfg.notes.push(`config: bad testCommands regex "${s}"`);
      }
    }
  }
  for (const k of ['tests', 'fixed']) {
    const v = parsed.claimPhrases?.[k];
    if (Array.isArray(v)) cfg.claimPhrases[k] = v.filter((x) => typeof x === 'string' && x.trim()).map((x) => x.toLowerCase());
  }
  if (Number.isInteger(parsed.maxBlocksPerSession) && parsed.maxBlocksPerSession >= 0) cfg.maxBlocksPerSession = parsed.maxBlocksPerSession;
  if (typeof parsed.commitLedger === 'boolean') cfg.commitLedger = parsed.commitLedger;
  return cfg;
}
