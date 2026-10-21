import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const NPM_DEFAULT_TEST = 'echo "Error: no test specified" && exit 1';

// Fixed argv, no user input: a shell on win32 is only there so npm .cmd shims (codex) resolve.
function spawnVersion(cmd) {
  const r = spawnSync(cmd, ['--version'], {
    encoding: 'utf8',
    timeout: 3000,
    shell: process.platform === 'win32',
  });
  if (r.error || r.status !== 0) return null;
  return (r.stdout || '').trim().split('\n')[0] || null;
}

export function checkSystem({ run = spawnVersion } = {}) {
  const probe = (cmd) => {
    const version = run(cmd);
    return { ok: Boolean(version), version };
  };
  const node = probe('node');
  node.ok = node.ok && parseInt(node.version.replace(/^v/, ''), 10) >= 18;
  return { node, git: probe('git'), claude: probe('claude'), codex: probe('codex') };
}

const read = (dir, file) => {
  const p = join(dir, file);
  return existsSync(p) ? readFileSync(p, 'utf8') : null;
};

export function detectTests(dir) {
  const found = [];
  const pkg = read(dir, 'package.json');
  if (pkg !== null) {
    let test;
    try { test = JSON.parse(pkg).scripts?.test; } catch { /* invalid package.json: no npm runner */ }
    if (typeof test === 'string' && test.trim() !== NPM_DEFAULT_TEST) {
      found.push({ file: 'package.json', command: 'npm test', regex: String.raw`^npm (run )?test\b` });
    }
  }
  const py = read(dir, 'pyproject.toml');
  if (py !== null && (py.includes('pytest') || py.includes('[tool.pytest'))) {
    found.push({ file: 'pyproject.toml', command: 'pytest', regex: String.raw`\bpytest\b` });
  }
  if (existsSync(join(dir, 'go.mod'))) {
    found.push({ file: 'go.mod', command: 'go test ./...', regex: String.raw`^go test\b` });
  }
  if (existsSync(join(dir, 'Cargo.toml'))) {
    found.push({ file: 'Cargo.toml', command: 'cargo test', regex: String.raw`^cargo test\b` });
  }
  const mk = read(dir, 'Makefile');
  if (mk !== null && /^test\s*:/m.test(mk)) {
    found.push({ file: 'Makefile', command: 'make test', regex: String.raw`^make test\b` });
  }
  return found;
}
