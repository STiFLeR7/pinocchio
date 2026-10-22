// `pinocchio uninstall`: removes exactly what setup recorded in install.json; the ledger is user data and stays.
import { existsSync, readdirSync, readFileSync, rmSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, isAbsolute, relative, resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { createUI } from './ui.js';
import { claudeCli } from './claude.js';
import { findState, hookSettingsFiles, runtimeRoot, within, writeState, sha256File } from './state.js';
import { unregisterHook } from './fallback.js';

const inside = (base, p) => { const r = relative(base, p); return r && !r.startsWith('..') && !isAbsolute(r) ? r.replace(/\\/g, '/') : null; };
// The config setup writes, wherever the project is: only that file name in a .claude dir (removal is also hash-gated).
const isSetupConfig = (p) => /(^|\/)\.claude\/pinocchio\.json$/.test(resolve(p).replace(/\\/g, '/'));
// A settings.json that exists but cannot be read as JSON (a missing file is fine).
const invalidJson = (file) => {
  try { JSON.parse(readFileSync(file, 'utf8').replace(/^﻿/, '')); return false; } catch (e) { return e.code !== 'ENOENT'; }
};

export function uninstall({ cwd = process.cwd(), home = homedir(), argv = [], ui = createUI(), cli = claudeCli() } = {}) {
  let flags;
  try {
    flags = parseArgs({ args: argv, options: { scope: { type: 'string' } } }).values;
  } catch (e) {
    ui.line(`✖ ${e.message}`);
    return 1;
  }
  if (flags.scope && flags.scope !== 'project' && flags.scope !== 'user') { ui.line(`✖ --scope must be project or user (got "${flags.scope}")`); return 1; }
  const scope = (flags.scope ? [flags.scope] : ['project', 'user']).find((s) => findState(s, cwd, home));
  if (!scope) {
    ui.line('Nothing to remove — Pinocchio was not installed by setup here.');
    return 0;
  }
  const { file: stateFile, st, legacy } = findState(scope, cwd, home);
  const lines = [];
  const show = (p) => inside(cwd, p) ?? (inside(home, p) ? `~/${inside(home, p)}` : p);
  const fail = (...ls) => { ui.box('Pinocchio uninstall', 'failed', ls); return 1; };

  // The state file is plain JSON a user may have edited: only ever touch paths setup could have written.
  const settingsOk = hookSettingsFiles(scope, cwd, home, legacy).map((p) => resolve(p));
  const bad = [
    st.runtime && !within(runtimeRoot(stateFile), st.runtime) && `runtime ${st.runtime}`,
    ...(st.files ?? []).filter((f) => !isSetupConfig(f.path)).map((f) => `file ${f.path}`),
    st.settings && !settingsOk.includes(resolve(st.settings.file)) && `settings ${st.settings.file}`,
  ].filter(Boolean);
  if (bad.length) return fail(`✖ install record names paths setup would not write: ${bad.join(', ')}`, `Nothing was removed. Check or delete ${show(stateFile)} by hand.`);

  // Registrations first, saving progress after each: a failure deletes nothing and a retry skips what is already gone.
  // (A settings install can still own a marketplace or plugin added by an earlier run.)
  const steps = [];
  if (st.addedPlugin) steps.push(['plugin removed', 'claude plugin uninstall', 'addedPlugin', () => cli.uninstall(scope), () => {
    const l = cli.listPlugins();
    return l.ok && Array.isArray(l.json) && !l.json.some((p) => p?.id === 'pinocchio@pinocchio');
  }]);
  else if (st.removedPlugin) lines.push('✔ plugin already removed');
  else if (st.method === 'plugin') lines.push('✔ kept pinocchio plugin (installed outside setup)');
  if (st.addedMarketplace) steps.push(['marketplace removed', 'claude plugin marketplace remove', 'addedMarketplace', () => cli.marketplaceRemove(scope), () => false]);
  else if (st.removedMarketplace) lines.push('✔ marketplace already removed');
  for (const [done, what, key, run, gone] of steps) {
    if (gone()) lines.push(`✔ ${done} (already gone)`);
    else {
      const r = run();
      if (!r.ok) return fail(...lines, `✖ ${what} failed: ${(r.stderr || '').trim().split('\n')[0] || 'no details'}`, 'Nothing else was removed. Fix the above and run: pinocchio uninstall');
      lines.push(`✔ ${done}`);
    }
    st[key] = false;
    st[key.replace('added', 'removed')] = true;
    writeState(stateFile, st);
  }
  if (st.settings) {
    const { file, hookCommand } = st.settings;
    let removed;
    try { removed = unregisterHook(file, hookCommand); } catch (e) { return fail(`✖ ${show(file)}: ${e.message}, so the Stop hook was left in place`, 'Nothing else was removed. Fix the above and run: pinocchio uninstall'); }
    if (removed) lines.push('✔ Stop hook removed');
    else if (invalidJson(file)) return fail(`✖ ${show(file)} is not plain JSON, so the Stop hook was left in place`, 'Nothing else was removed. Remove the pinocchio hook by hand, then run: pinocchio uninstall');
    else lines.push('✔ Stop hook already gone');
  }

  for (const f of st.files ?? []) {
    if (!existsSync(f.path)) continue;
    if (sha256File(f.path) === f.sha256) { rmSync(f.path, { force: true }); lines.push(`✔ removed ${show(f.path)}`); }
    else lines.push(`✔ kept ${show(f.path)} (changed since setup)`);
  }
  if (st.runtime) { rmSync(st.runtime, { recursive: true, force: true }); lines.push('✔ runtime copy removed'); }
  rmSync(stateFile, { force: true });
  // Setup's own folder goes too once only its .gitignore is left; the ledger dir is never touched.
  const own = dirname(stateFile);
  if (!legacy && readdirSync(own).every((f) => f === '.gitignore')) rmSync(own, { recursive: true, force: true });
  lines.push('✔ install record removed', '✔ ledger kept at .claude/pinocchio/');
  ui.box('Pinocchio uninstall', 'done', lines);
  const other = scope === 'user' ? 'project' : 'user';
  if (findState(other, cwd, home)) ui.line(`${other}-scope install also recorded; run: npx @stifler7/pinocchio uninstall --scope ${other}`);
  return 0;
}
