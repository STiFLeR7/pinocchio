// `pinocchio doctor`: checks the install and prints one fix line per failed check.
import { homedir } from 'node:os';
import { createUI } from './ui.js';
import { checkSystem } from './detect.js';
import { claudeCli } from './claude.js';
import { statePath, readState } from './state.js';
import { hasHook } from './fallback.js';
import { loadConfig } from '../src/config.js';
import { verifyChain } from '../src/ledger.js';

const SETUP = 'run: npx @stifler7/pinocchio setup';
const PLUGIN = 'pinocchio@pinocchio';

function registration(cwd, home, cli) {
  const r = cli.listPlugins();
  const plugin = r.ok && Array.isArray(r.json) ? r.json.find((p) => p?.id === PLUGIN) : null;
  if (plugin) {
    return plugin.enabled === false
      ? { ok: false, text: 'plugin installed but disabled', fix: `run: claude plugin enable ${PLUGIN}` }
      : { ok: true, text: 'plugin registered (pinocchio@pinocchio)' };
  }
  for (const scope of ['project', 'user']) {
    const st = readState(statePath(scope, cwd, home));
    if (st?.method === 'settings' && st.settings && hasHook(st.settings.file, st.settings.hookCommand)) {
      return { ok: true, text: `Stop hook registered (${scope} settings.json)` };
    }
  }
  return { ok: false, text: 'not registered with Claude Code', fix: SETUP };
}

export function doctor({ cwd = process.cwd(), home = homedir(), ui = createUI(), cli = claudeCli(), system } = {}) {
  const { node, git } = system ?? checkSystem();
  const notes = loadConfig(cwd).notes;
  const chain = verifyChain(cwd);
  const checks = [
    { ok: node.ok, text: `Node ${node.version ?? 'not found'} (18 or newer needed)`, fix: 'install Node 18 or newer — https://nodejs.org' },
    { ok: git.ok, text: `git ${git.version ?? 'not found'}`, fix: 'install git — https://git-scm.com' },
    registration(cwd, home, cli),
    notes.length
      ? { ok: false, text: `config: ${notes.join('; ')}`, fix: 'fix .claude/pinocchio.json (or delete it and run: npx @stifler7/pinocchio setup)' }
      : { ok: true, text: 'config ok' },
    chain.ok
      ? { ok: true, text: chain.count ? `ledger hash chain intact (${chain.count} entries)` : 'no ledger yet' }
      : { ok: false, text: `ledger hash chain broken at entry ${chain.brokenAt}`, fix: 'inspect .claude/pinocchio/ledger.jsonl; move it aside to start a fresh chain' },
  ];
  const failed = checks.filter((c) => !c.ok);
  ui.box('Pinocchio doctor', failed.length ? 'failed' : 'done',
    checks.flatMap((c) => [`${c.ok ? '✔' : '✖'} ${c.text}`, ...(c.ok ? [] : [`  fix: ${c.fix}`])]));
  ui.line(failed.length ? `${failed.length} problem${failed.length > 1 ? 's' : ''} found.` : 'All good.');
  return failed.length ? 1 : 0;
}
