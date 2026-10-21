import { spawnSync } from 'node:child_process';

const REPO = 'STiFLeR7/pinocchio';
const PLUGIN = 'pinocchio@pinocchio';

// No shell: `claude` is a real executable on every platform. A .js/.mjs bin is a test seam run via node.
export function claudeCli({ bin = process.env.PINOCCHIO_CLAUDE || 'claude' } = {}) {
  const run = (args) => {
    const [cmd, argv] = /\.m?js$/.test(bin) ? [process.execPath, [bin, ...args]] : [bin, args];
    const r = spawnSync(cmd, argv, { encoding: 'utf8', timeout: 60000 });
    if (r.error) return { ok: false, json: null, stderr: r.error.message };
    let json = null;
    try { json = JSON.parse(r.stdout); } catch { /* non-JSON output */ }
    return { ok: r.status === 0, json, stderr: r.stderr || '' };
  };
  const plugin = (...a) => run(['plugin', ...a, '--json']);
  return {
    marketplaceAdd: (scope) => plugin('marketplace', 'add', REPO, '--scope', scope),
    install: (scope) => plugin('install', PLUGIN, '--scope', scope, '-y'),
    uninstall: (scope) => plugin('uninstall', PLUGIN, '--scope', scope),
    marketplaceRemove: (scope) => plugin('marketplace', 'remove', 'pinocchio', '--scope', scope),
    listPlugins: () => plugin('list'),
  };
}
