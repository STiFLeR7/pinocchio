// Fallback registration: a Stop hook in a Claude Code settings.json, for when `claude plugin` is missing or fails.
import { mkdirSync, readFileSync, realpathSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { basename, dirname } from 'node:path';

const BOM = '﻿';
export const hookGroup = (command) => ({ hooks: [{ type: 'command', command, timeout: 5 }] });

// Missing file reads as {}; anything that is not a plain JSON object (comments, trailing commas, arrays) is refused.
// A leading BOM and CRLF line endings are remembered so the rewrite keeps them.
function read(file) {
  const name = basename(file);
  let raw;
  try { raw = readFileSync(file, 'utf8'); } catch (e) { return e.code === 'ENOENT' ? { settings: {}, style: {} } : { reason: `cannot read ${name}: ${e.code}` }; }
  const style = { bom: raw.startsWith(BOM), crlf: raw.includes('\r\n') };
  let settings;
  try { settings = JSON.parse(style.bom ? raw.slice(1) : raw); } catch { return { reason: `${name} is not plain JSON` }; }
  if (!settings || typeof settings !== 'object' || Array.isArray(settings)) return { reason: `${name} is not a JSON object` };
  const stop = settings.hooks?.Stop;
  if ((settings.hooks !== undefined && (typeof settings.hooks !== 'object' || Array.isArray(settings.hooks))) || (stop !== undefined && !Array.isArray(stop))) {
    return { reason: `${name} hooks.Stop is not a list` };
  }
  return { settings, style };
}

// Temp file next to the real target + rename: a crash mid-write never leaves a truncated settings.json,
// and a symlinked settings.json (dotfiles) stays a symlink. On failure the temp file is removed and the error rethrown.
function write(file, settings, { bom, crlf }, rename = renameSync) {
  const text = JSON.stringify(settings, null, 2) + '\n';
  let target = file;
  try { target = realpathSync(file); } catch { /* missing: write it where it was asked for */ }
  const tmp = `${target}.${process.pid}.tmp`;
  try {
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(tmp, (bom ? BOM : '') + (crlf ? text.replace(/\n/g, '\r\n') : text));
    rename(tmp, target);
  } catch (e) {
    rmSync(tmp, { force: true });
    throw new Error(`cannot write ${basename(file)}: ${e.code ?? e.message}`);
  }
}

const has = (settings, command) => (settings.hooks?.Stop ?? []).some((g) => g?.hooks?.some?.((h) => h?.command === command));

export function hasHook(file, command) {
  const { settings } = read(file);
  return Boolean(settings && has(settings, command));
}

// `rename` is a test seam for a failing write.
export function registerHook(file, command, { rename } = {}) {
  const { settings, style, reason } = read(file);
  if (!settings) return { ok: false, reason };
  if (has(settings, command)) return { ok: true };
  settings.hooks ??= {};
  settings.hooks.Stop ??= [];
  settings.hooks.Stop.push(hookGroup(command));
  try { write(file, settings, style, rename); } catch (e) { return { ok: false, reason: e.message }; }
  return { ok: true };
}

// Removes only hooks with exactly this command; groups, Stop and hooks left empty by that are dropped too.
// Throws if the rewrite fails (the file is left as it was).
export function unregisterHook(file, command, { rename } = {}) {
  const { settings, style } = read(file);
  if (!settings || !has(settings, command)) return false;
  const stop = settings.hooks.Stop
    .map((g) => (Array.isArray(g?.hooks) ? { ...g, hooks: g.hooks.filter((h) => h?.command !== command) } : g))
    .filter((g) => !Array.isArray(g?.hooks) || g.hooks.length);
  if (stop.length) settings.hooks.Stop = stop;
  else delete settings.hooks.Stop;
  if (!Object.keys(settings.hooks).length) delete settings.hooks;
  write(file, settings, style, rename);
  return true;
}
