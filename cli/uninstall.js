// `pinocchio uninstall`: removes exactly what setup recorded in install.json; the ledger is user data and stays.
import { existsSync, rmSync } from 'node:fs';
import { homedir } from 'node:os';
import { isAbsolute, relative } from 'node:path';
import { parseArgs } from 'node:util';
import { createUI } from './ui.js';
import { claudeCli } from './claude.js';
import { statePath, readState, sha256File } from './state.js';
import { unregisterHook } from './fallback.js';

const inside = (base, p) => { const r = relative(base, p); return r && !r.startsWith('..') && !isAbsolute(r) ? r.replace(/\\/g, '/') : null; };

export function uninstall({ cwd = process.cwd(), home = homedir(), argv = [], ui = createUI(), cli = claudeCli() } = {}) {
  let flags;
  try {
    flags = parseArgs({ args: argv, options: { scope: { type: 'string' } } }).values;
  } catch (e) {
    ui.line(`✖ ${e.message}`);
    return 1;
  }
  if (flags.scope && flags.scope !== 'project' && flags.scope !== 'user') { ui.line(`✖ --scope must be project or user (got "${flags.scope}")`); return 1; }
  const scope = (flags.scope ? [flags.scope] : ['project', 'user']).find((s) => readState(statePath(s, cwd, home)));
  if (!scope) {
    ui.line('Nothing to remove — Pinocchio was not installed by setup here.');
    return 0;
  }
  const stateFile = statePath(scope, cwd, home);
  const st = readState(stateFile);
  const lines = [];
  const show = (p) => inside(cwd, p) ?? (inside(home, p) ? `~/${inside(home, p)}` : p);

  if (st.method === 'plugin') {
    // Registrations first: if the claude CLI refuses, nothing is deleted and the state stays for a retry.
    const steps = [];
    if (st.addedPlugin) steps.push(['plugin removed', 'claude plugin uninstall', () => cli.uninstall(scope)]);
    else lines.push('✔ kept pinocchio plugin (installed outside setup)');
    if (st.addedMarketplace) steps.push(['marketplace removed', 'claude plugin marketplace remove', () => cli.marketplaceRemove(scope)]);
    for (const [done, what, run] of steps) {
      const r = run();
      if (!r.ok) {
        ui.box('Pinocchio uninstall', 'failed', [...lines, `✖ ${what} failed: ${(r.stderr || '').trim().split('\n')[0] || 'no details'}`, 'Nothing else was removed. Fix the above and run: pinocchio uninstall']);
        return 1;
      }
      lines.push(`✔ ${done}`);
    }
  } else if (st.settings) {
    lines.push(unregisterHook(st.settings.file, st.settings.hookCommand) ? '✔ Stop hook removed' : '✔ Stop hook already gone');
  }

  for (const f of st.files ?? []) {
    if (!existsSync(f.path)) continue;
    if (sha256File(f.path) === f.sha256) { rmSync(f.path, { force: true }); lines.push(`✔ removed ${show(f.path)}`); }
    else lines.push(`✔ kept ${show(f.path)} (changed since setup)`);
  }
  if (st.runtime) { rmSync(st.runtime, { recursive: true, force: true }); lines.push('✔ runtime copy removed'); }
  rmSync(stateFile, { force: true });
  lines.push('✔ install record removed', '✔ ledger kept at .claude/pinocchio/');
  ui.box('Pinocchio uninstall', 'done', lines);
  return 0;
}
