import { spawnSync } from 'node:child_process';

const REPO = 'STiFLeR7/pinocchio';
const PLUGIN = 'pinocchio@pinocchio';
const OPTS = { encoding: 'utf8', timeout: 60000 };

// Whole stdout first, then the last non-empty line (the CLI may print a note before the JSON).
function parseJson(out) {
  for (const s of [out, (out || '').trim().split('\n').pop()]) {
    try { return JSON.parse(s); } catch { /* try next */ }
  }
  return null;
}

// A .js/.mjs bin is a test seam run via node. On win32 an npm-installed claude is claude.cmd, which needs a shell:
// one command string (no args array: DEP0190); safe because every argument is a constant and scope is validated.
export function claudeCli({ bin = process.env.PINOCCHIO_CLAUDE || 'claude' } = {}) {
  const viaNode = /\.m?js$/.test(bin);
  const viaShell = process.platform === 'win32' && !viaNode && !/\.exe$/i.test(bin);
  const run = (args) => {
    const r = viaNode ? spawnSync(process.execPath, [bin, ...args], OPTS)
      : viaShell ? spawnSync([/\s/.test(bin) ? `"${bin}"` : bin, ...args].join(' '), { ...OPTS, shell: true })
      : spawnSync(bin, args, OPTS);
    if (r.error) return { ok: false, json: null, stderr: r.error.message };
    return { ok: r.status === 0, json: parseJson(r.stdout), stderr: r.stderr || '' };
  };
  const plugin = (scope, a, after = []) => {
    if (scope !== 'user' && scope !== 'project') throw new Error(`invalid scope: ${scope}`);
    return run(['plugin', ...a, '--scope', scope, ...after, '--json']);
  };
  return {
    marketplaceAdd: (scope) => plugin(scope, ['marketplace', 'add', REPO]),
    install: (scope) => plugin(scope, ['install', PLUGIN], ['-y']),
    uninstall: (scope) => plugin(scope, ['uninstall', PLUGIN]),
    marketplaceRemove: (scope) => plugin(scope, ['marketplace', 'remove', 'pinocchio']),
    listPlugins: () => run(['plugin', 'list', '--json']),
    listMarketplaces: () => run(['plugin', 'marketplace', 'list', '--json']),
  };
}
