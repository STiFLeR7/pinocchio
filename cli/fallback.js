// Fallback registration: a Stop hook in a Claude Code settings.json, for when `claude plugin` is missing or fails.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

export const hookGroup = (command) => ({ hooks: [{ type: 'command', command, timeout: 5 }] });

// Missing file reads as {}; anything that is not a plain JSON object (comments, trailing commas, arrays) is refused.
function read(file) {
  let raw;
  try { raw = readFileSync(file, 'utf8'); } catch (e) { return e.code === 'ENOENT' ? { settings: {} } : { reason: `cannot read settings.json: ${e.code}` }; }
  let settings;
  try { settings = JSON.parse(raw); } catch { return { reason: 'settings.json is not plain JSON' }; }
  if (!settings || typeof settings !== 'object' || Array.isArray(settings)) return { reason: 'settings.json is not a JSON object' };
  const stop = settings.hooks?.Stop;
  if ((settings.hooks !== undefined && (typeof settings.hooks !== 'object' || Array.isArray(settings.hooks))) || (stop !== undefined && !Array.isArray(stop))) {
    return { reason: 'settings.json hooks.Stop is not a list' };
  }
  return { settings };
}

const write = (file, settings) => {
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, JSON.stringify(settings, null, 2) + '\n');
};

const has = (settings, command) => (settings.hooks?.Stop ?? []).some((g) => g?.hooks?.some?.((h) => h?.command === command));

export function hasHook(file, command) {
  const { settings } = read(file);
  return Boolean(settings && has(settings, command));
}

export function registerHook(file, command) {
  const { settings, reason } = read(file);
  if (!settings) return { ok: false, reason };
  if (has(settings, command)) return { ok: true };
  settings.hooks ??= {};
  settings.hooks.Stop ??= [];
  settings.hooks.Stop.push(hookGroup(command));
  write(file, settings);
  return { ok: true };
}

// Removes only hooks with exactly this command; groups, Stop and hooks left empty by that are dropped too.
export function unregisterHook(file, command) {
  const { settings } = read(file);
  if (!settings || !has(settings, command)) return false;
  const stop = settings.hooks.Stop
    .map((g) => (Array.isArray(g?.hooks) ? { ...g, hooks: g.hooks.filter((h) => h?.command !== command) } : g))
    .filter((g) => !Array.isArray(g?.hooks) || g.hooks.length);
  if (stop.length) settings.hooks.Stop = stop;
  else delete settings.hooks.Stop;
  if (!Object.keys(settings.hooks).length) delete settings.hooks;
  write(file, settings);
  return true;
}
